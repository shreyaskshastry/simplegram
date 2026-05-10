# Simplegram Backend API

Base URL: `http://localhost:8000`

Endpoints:
- `POST /images/upload` — multipart form: `file` (binary), `tag` (string), `description` (string). Returns stored image metadata including `ImageId`.
- `GET /images` — list images. Optional query params: `tag` (prefix), `q` (description prefix), `since` (ISO timestamp), `until` (ISO timestamp).
- `GET /images/search/{prefix}` — search Tag or Description by prefix.
- `GET /images/download/{img_id}` — returns `presigned_url` for download.
- `DELETE /images/{img_id}` — deletes image (processed + original) and metadata.
- `GET /admin/stats` — returns counters for `uploads`, `downloads`, `deletes`.
- `GET /admin/logs` — returns recent logs.

Notes:
- Service expects an S3 bucket `my-bucket` and DynamoDB tables `Images`, `Logs`, `Stats`.
- For local development use Localstack (docker-compose included).

Usage Instructions
- Clone the Repo
- Ensure PIL and pillow folder is present inside lambda folder if not run `pip install Pillow -t`
- Make sure docker is running in the system
- Run the command `cd simplegram`
- Run the command `docker compose build`
- Run the command `docker compose up -d`
- Head to `localhost:5173`to access the simplegram UI
- To bring down the app , Run the command `docker compose down`

API Docs
- Run the App
- http://localhost:8000/docs