import os, uuid
from datetime import datetime
from typing import Optional
from boto3.dynamodb.conditions import Attr
import boto3
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import ClientError

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- AWS Config ---
# For backend-to-localstack communication inside Docker
ENDPOINT = os.getenv("AWS_ENDPOINT", "http://localstack:4566")

s3 = boto3.client('s3', endpoint_url=ENDPOINT, region_name="us-east-1")
dynamo = boto3.resource('dynamodb', endpoint_url=ENDPOINT, region_name="us-east-1")

table_img = dynamo.Table('Images')
table_logs = dynamo.Table('Logs')
table_stats = dynamo.Table('Stats')

def track_event(event: str, msg: str):
    if event in ['uploads', 'downloads', 'deletes']:
        table_stats.update_item(
            Key={'StatName': event},
            UpdateExpression="ADD #v :i",
            ExpressionAttributeNames={'#v': 'Value'},
            ExpressionAttributeValues={':i': 1}
        )
    table_logs.put_item(Item={
        'LogId': str(uuid.uuid4()),
        'Timestamp': datetime.utcnow().isoformat(),
        'Event': event,
        'Message': msg
    })

@app.post("/images/upload")
async def upload(file: UploadFile = File(...), tag: str = Form(...), description: str = Form(...)):
    img_id = str(uuid.uuid4())
    
    filename = file.filename.replace(" ", "_") # Clean filename
    s3_key = f"uploads/{img_id}-{filename}"
    
    try:
        s3.upload_fileobj(file.file, "my-bucket", s3_key)

        processed_key = s3_key.replace("uploads/", "processed/")
        
        item = {
            'ImageId': img_id, 
            'S3Key': processed_key, # Link to the resized version
            'Tag': tag, 
            'Description': description,
            'OriginalKey': s3_key,
            'Timestamp': datetime.utcnow().isoformat()
        }
        
        table_img.put_item(Item=item)
        track_event("uploads", f"Uploaded {file.filename}")
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/images")
async def list_imgs(tag: Optional[str] = None, q: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None):
    filter_expr = None
    if tag:
        # allow prefix search on Tag
        filter_expr = Attr('Tag').begins_with(tag)
    if q:
        # allow prefix search on Description
        expr = Attr('Description').begins_with(q)
        filter_expr = expr if filter_expr is None else (filter_expr & expr)
    if since:
        expr = Attr('Timestamp').gte(since)
        filter_expr = expr if filter_expr is None else (filter_expr & expr)
    if until:
        expr = Attr('Timestamp').lte(until)
        filter_expr = expr if filter_expr is None else (filter_expr & expr)

    if filter_expr is not None:
        items = table_img.scan(FilterExpression=filter_expr)['Items']
    else:
        items = table_img.scan()['Items']
    
    for i in items:
        key_to_use = i.get('S3Key')
        try:
            s3.head_object(Bucket='my-bucket', Key=key_to_use)
        except ClientError as e:
            err_code = e.response.get('Error', {}).get('Code')
            if err_code in ('404', 'NoSuchKey', 'NotFound', 'NoSuchBucket'):
                key_to_use = i.get('OriginalKey', key_to_use)
            else:
                raise

        # Generate URL using internal endpoint, then swap to localhost for the browser
        raw_url = s3.generate_presigned_url(
            'get_object', 
            Params={'Bucket': 'my-bucket', 'Key': key_to_use}, 
            ExpiresIn=3600
        )
        i['Url'] = raw_url.replace("localstack", "localhost")
        
    return sorted(items, key=lambda x: x.get('Timestamp', ''), reverse=True)


@app.get("/images/search/{prefix}")
async def search_prefix(prefix: str):
    # Search both Tag and Description for prefix (OR)
    filter_expr = Attr('Tag').begins_with(prefix) | Attr('Description').begins_with(prefix)
    items = table_img.scan(FilterExpression=filter_expr)['Items']

    for i in items:
        key_to_use = i.get('S3Key')
        try:
            s3.head_object(Bucket='my-bucket', Key=key_to_use)
        except ClientError as e:
            err_code = e.response.get('Error', {}).get('Code')
            if err_code in ('404', 'NoSuchKey', 'NotFound', 'NoSuchBucket'):
                key_to_use = i.get('OriginalKey', key_to_use)
            else:
                raise

        raw_url = s3.generate_presigned_url(
            'get_object', 
            Params={'Bucket': 'my-bucket', 'Key': key_to_use}, 
            ExpiresIn=3600
        )
        i['Url'] = raw_url.replace("localstack", "localhost")

    return sorted(items, key=lambda x: x.get('Timestamp', ''), reverse=True)

@app.get("/images/download/{img_id}")
async def download(img_id: str):
    # Return a presigned URL for the requested image (processed preferred)
    res = table_img.get_item(Key={'ImageId': img_id})
    if 'Item' not in res:
        raise HTTPException(status_code=404, detail="Image not found")

    item = res['Item']
    key_to_use = item.get('S3Key')
    try:
        s3.head_object(Bucket='my-bucket', Key=key_to_use)
    except ClientError as e:
        err_code = e.response.get('Error', {}).get('Code')
        if err_code in ('404', 'NoSuchKey', 'NotFound', 'NoSuchBucket'):
            key_to_use = item.get('OriginalKey', key_to_use)
        else:
            raise

    raw_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': 'my-bucket', 'Key': key_to_use},
        ExpiresIn=3600
    )

    track_event("downloads", f"Downloaded image {img_id}")
    return {"presigned_url": raw_url.replace("localstack", "localhost")}

@app.delete("/images/{img_id}")
async def delete_img(img_id: str):
    res = table_img.get_item(Key={'ImageId': img_id})
    if 'Item' in res:
        # Delete both original and processed
        item = res['Item']
        s3.delete_object(Bucket="my-bucket", Key=item['S3Key'])
        if 'OriginalKey' in item:
            s3.delete_object(Bucket="my-bucket", Key=item['OriginalKey'])
            
        table_img.delete_item(Key={'ImageId': img_id})
        track_event("deletes", f"Deleted {img_id}")
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Image not found")

@app.get("/admin/stats")
async def get_stats():
    res = table_stats.scan()['Items']
    return {item['StatName']: int(item['Value']) for item in res}

@app.get("/admin/logs")
async def get_logs():
    res = table_logs.scan()['Items']
    return sorted(res, key=lambda x: x['Timestamp'], reverse=True)