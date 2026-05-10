import boto3
import io
from PIL import Image

s3 = boto3.client('s3', endpoint_url="http://localstack:4566")

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        if not key.startswith('uploads/'):
            continue
            
        print(f"Resizing {key}...")
        response = s3.get_object(Bucket=bucket, Key=key)
        img = Image.open(io.BytesIO(response['Body'].read()))
        
        # Exact resize requested
        img = img.resize((450, 190))
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        
        processed_key = key.replace('uploads/', 'processed/')
        s3.put_object(Bucket=bucket, Key=processed_key, Body=buffer, ContentType='image/jpeg')
        print(f"Done: {processed_key}")