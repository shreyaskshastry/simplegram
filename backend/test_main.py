import io
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

os.environ["AWS_DEFAULT_REGION"]    = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"]     = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"]    = "testing"
os.environ["AWS_SESSION_TOKEN"]     = "testing"

os.environ["AWS_ENDPOINT"] = "http://localhost:5000"


def _bootstrap_aws():
    """Create S3 bucket + DynamoDB tables inside the active moto context."""
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="my-bucket")
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    for table_name, pk in [("Images", "ImageId"), ("Logs", "LogId"), ("Stats", "StatName")]:
        ddb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": pk, "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )


@pytest.fixture(scope="session", autouse=True)
def start_moto():
    """
    Start moto for the whole session, then import main so that its module-level
    boto3 clients are created inside the mock (not against localstack).
    """
    mock = mock_aws()
    mock.start()
    _bootstrap_aws()

    # Force a fresh import even if a previous failed attempt cached a partial module
    sys.modules.pop("main", None)

    import main as _main

    # Re-point main's module-level clients at the moto-backed resource
    # (moto intercepts regardless of endpoint_url, but this ensures no stale references)
    _main.s3 = boto3.client("s3", region_name="us-east-1")
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    _main.table_img   = ddb.Table("Images")
    _main.table_logs  = ddb.Table("Logs")
    _main.table_stats = ddb.Table("Stats")

    yield _main
    mock.stop()


@pytest.fixture(autouse=True)
def clean_tables():
    """Wipe all data before each individual test."""
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    s3  = boto3.client("s3",         region_name="us-east-1")

    for table_name, pk in [("Images", "ImageId"), ("Logs", "LogId"), ("Stats", "StatName")]:
        table = ddb.Table(table_name)
        for item in table.scan()["Items"]:
            table.delete_item(Key={pk: item[pk]})

    for obj in s3.list_objects_v2(Bucket="my-bucket").get("Contents", []):
        s3.delete_object(Bucket="my-bucket", Key=obj["Key"])


@pytest.fixture()
def client(start_moto):
    from fastapi.testclient import TestClient
    return TestClient(start_moto.app)


# ── Shared upload helper ───────────────────────────────────────────────────────

def _upload(client, filename="photo.jpg", tag="nature", description="A lake"):
    return client.post(
        "/images/upload",
        data={"tag": tag, "description": description},
        files={"file": (filename, io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /images/upload
# ══════════════════════════════════════════════════════════════════════════════

class TestUpload:

    def test_upload_success_returns_image_metadata(self, client):
        resp = _upload(client)
        assert resp.status_code == 200
        body = resp.json()
        assert "ImageId" in body
        assert body["Tag"] == "nature"
        assert body["Description"] == "A lake"
        assert "S3Key" in body
        assert "OriginalKey" in body
        assert "Timestamp" in body

    def test_upload_stores_original_and_processed_keys(self, client):
        body = _upload(client, filename="my photo.jpg").json()
        assert " " not in body["OriginalKey"]
        assert body["OriginalKey"].startswith("uploads/")
        assert body["S3Key"].startswith("processed/")

    def test_upload_increments_uploads_stat(self, client):
        _upload(client)
        assert client.get("/admin/stats").json().get("uploads", 0) == 1

    def test_upload_writes_log_entry(self, client):
        _upload(client)
        events = [l["Event"] for l in client.get("/admin/logs").json()]
        assert "uploads" in events

    def test_multiple_uploads_tracked_separately(self, client):
        _upload(client, tag="a")
        _upload(client, tag="b")
        assert client.get("/admin/stats").json()["uploads"] == 2

    def test_upload_s3_failure_returns_500(self, client, start_moto):
        original = start_moto.s3.upload_fileobj
        start_moto.s3.upload_fileobj = MagicMock(side_effect=Exception("S3 down"))
        try:
            assert _upload(client).status_code == 500
        finally:
            start_moto.s3.upload_fileobj = original


# ══════════════════════════════════════════════════════════════════════════════
# GET /images
# ══════════════════════════════════════════════════════════════════════════════

class TestListImages:

    def test_list_returns_all_images(self, client):
        _upload(client, tag="dogs")
        _upload(client, tag="cats")
        assert len(client.get("/images").json()) == 2

    def test_list_empty_when_no_uploads(self, client):
        assert client.get("/images").json() == []

    def test_filter_by_tag_prefix(self, client):
        _upload(client, tag="nature")
        _upload(client, tag="night")
        _upload(client, tag="dogs")
        items = client.get("/images?tag=na").json()
        assert len(items) == 1
        assert items[0]["Tag"] == "nature"

    def test_filter_by_description_prefix(self, client):
        _upload(client, description="Sunny beach")
        _upload(client, description="Dark cave")
        items = client.get("/images?q=Sunny").json()
        assert len(items) == 1
        assert items[0]["Description"].startswith("Sunny")

    def test_combined_tag_and_description_filter(self, client):
        _upload(client, tag="nature", description="Sunny beach")
        _upload(client, tag="nature", description="Dark cave")
        assert len(client.get("/images?tag=nature&q=Sunny").json()) == 1

    def test_results_sorted_newest_first(self, client):
        _upload(client, tag="first")
        _upload(client, tag="second")
        ts = [i["Timestamp"] for i in client.get("/images").json()]
        assert ts == sorted(ts, reverse=True)

    def test_items_have_presigned_url(self, client):
        _upload(client)
        items = client.get("/images").json()
        assert "Url" in items[0]
        assert items[0]["Url"].startswith("http")

    def test_filter_since_future_returns_empty(self, client):
        _upload(client, tag="old")
        assert client.get("/images?since=2099-01-01T00:00:00").json() == []

    def test_filter_until_past_returns_empty(self, client):
        _upload(client, tag="new")
        assert client.get("/images?until=2000-01-01T00:00:00").json() == []


# ══════════════════════════════════════════════════════════════════════════════
# GET /images/search/{prefix}
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchPrefix:

    def test_search_matches_tag(self, client):
        _upload(client, tag="forest", description="Green trees")
        items = client.get("/images/search/for").json()
        assert len(items) == 1
        assert items[0]["Tag"] == "forest"

    def test_search_matches_description(self, client):
        _upload(client, tag="city", description="Urban jungle")
        assert len(client.get("/images/search/Urban").json()) == 1

    def test_search_no_match_returns_empty(self, client):
        _upload(client, tag="ocean", description="Blue water")
        assert client.get("/images/search/xyz").json() == []

    def test_search_result_has_url(self, client):
        _upload(client, tag="sunsets")
        assert "Url" in client.get("/images/search/sun").json()[0]

    def test_search_or_logic(self, client):
        _upload(client, tag="abc", description="xyz photo")
        assert len(client.get("/images/search/abc").json()) == 1
        assert len(client.get("/images/search/xyz").json()) == 1


# ══════════════════════════════════════════════════════════════════════════════
# GET /images/download/{img_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestDownload:

    def test_download_returns_presigned_url(self, client):
        img_id = _upload(client).json()["ImageId"]
        resp = client.get(f"/images/download/{img_id}")
        assert resp.status_code == 200
        assert resp.json()["presigned_url"].startswith("http")

    def test_download_increments_stat(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.get(f"/images/download/{img_id}")
        assert client.get("/admin/stats").json().get("downloads", 0) == 1

    def test_download_nonexistent_image_returns_404(self, client):
        assert client.get(f"/images/download/{uuid.uuid4()}").status_code == 404

    def test_download_writes_log(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.get(f"/images/download/{img_id}")
        events = {l["Event"] for l in client.get("/admin/logs").json()}
        assert "downloads" in events

    def test_download_falls_back_to_original_key(self, client):
        """Processed key won't exist in tests (no Lambda); falls back to OriginalKey."""
        img_id = _upload(client).json()["ImageId"]
        resp = client.get(f"/images/download/{img_id}")
        assert resp.status_code == 200
        assert "presigned_url" in resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /images/{img_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteImage:

    def test_delete_existing_image(self, client):
        img_id = _upload(client).json()["ImageId"]
        assert client.delete(f"/images/{img_id}").json() == {"status": "deleted"}

    def test_delete_removes_image_from_list(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.delete(f"/images/{img_id}")
        ids = [i["ImageId"] for i in client.get("/images").json()]
        assert img_id not in ids

    def test_delete_increments_stat(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.delete(f"/images/{img_id}")
        assert client.get("/admin/stats").json().get("deletes", 0) == 1

    def test_delete_nonexistent_returns_404(self, client):
        assert client.delete(f"/images/{uuid.uuid4()}").status_code == 404

    def test_delete_writes_log(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.delete(f"/images/{img_id}")
        events = {l["Event"] for l in client.get("/admin/logs").json()}
        assert "deletes" in events


# ══════════════════════════════════════════════════════════════════════════════
# GET /admin/stats
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminStats:

    def test_stats_empty_initially(self, client):
        assert client.get("/admin/stats").json() == {}

    def test_stats_accumulate_correctly(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.get(f"/images/download/{img_id}")
        client.delete(f"/images/{img_id}")
        stats = client.get("/admin/stats").json()
        assert stats["uploads"]   == 1
        assert stats["downloads"] == 1
        assert stats["deletes"]   == 1

    def test_stats_values_are_integers(self, client):
        _upload(client)
        for v in client.get("/admin/stats").json().values():
            assert isinstance(v, int)


# ══════════════════════════════════════════════════════════════════════════════
# GET /admin/logs
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminLogs:

    def test_logs_empty_initially(self, client):
        assert client.get("/admin/logs").json() == []

    def test_logs_contain_required_fields(self, client):
        _upload(client)
        for log in client.get("/admin/logs").json():
            assert {"LogId", "Timestamp", "Event", "Message"}.issubset(log)

    def test_logs_sorted_newest_first(self, client):
        _upload(client)
        img_id = _upload(client).json()["ImageId"]
        client.get(f"/images/download/{img_id}")
        ts = [l["Timestamp"] for l in client.get("/admin/logs").json()]
        assert ts == sorted(ts, reverse=True)

    def test_logs_capture_all_event_types(self, client):
        img_id = _upload(client).json()["ImageId"]
        client.get(f"/images/download/{img_id}")
        client.delete(f"/images/{img_id}")
        events = {l["Event"] for l in client.get("/admin/logs").json()}
        assert {"uploads", "downloads", "deletes"}.issubset(events)