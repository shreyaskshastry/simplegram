#!/bin/bash

# 1. Infrastructure Setup
awslocal s3 mb s3://my-bucket
# Add CORS so browser can GET objects from localstack
awslocal s3api put-bucket-cors --bucket my-bucket --cors-configuration '{"CORSRules":[{"AllowedHeaders":["*"],"AllowedMethods":["GET","HEAD","PUT","POST","DELETE"],"AllowedOrigins":["*"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":3000}]}'
awslocal dynamodb create-table --table-name Images --attribute-definitions AttributeName=ImageId,AttributeType=S --key-schema AttributeName=ImageId,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
awslocal dynamodb create-table --table-name Logs --attribute-definitions AttributeName=LogId,AttributeType=S --key-schema AttributeName=LogId,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
awslocal dynamodb create-table --table-name Stats --attribute-definitions AttributeName=StatName,AttributeType=S --key-schema AttributeName=StatName,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5

# 2. Stats Init
awslocal dynamodb put-item --table-name Stats --item '{"StatName": {"S": "uploads"}, "Value": {"N": "0"}}'
awslocal dynamodb put-item --table-name Stats --item '{"StatName": {"S": "downloads"}, "Value": {"N": "0"}}'
awslocal dynamodb put-item --table-name Stats --item '{"StatName": {"S": "deletes"}, "Value": {"N": "0"}}'

# 3. Lambda Setup
echo "Packaging Lambda from subfolder..."
# We go into the subfolder we defined in docker-compose (look for possible folder names)
if [ -d "/etc/localstack/init/ready.d/lambda_code" ]; then
    cd /etc/localstack/init/ready.d/lambda_code
elif [ -d "/etc/localstack/init/ready.d/lambda" ]; then
    cd /etc/localstack/init/ready.d/lambda
else
    cd /etc/localstack/init/ready.d/ || true
fi

    if [ -f "resize_handler.py" ]; then
    zip -r /tmp/lambda.zip .
    
    echo "Creating Lambda Function..."
    awslocal lambda create-function \
        --function-name ResizeImage \
        --runtime python3.11 \
        --handler resize_handler.handler \
        --role arn:aws:iam::000000000000:role/lambda-role \
        --zip-file fileb:///tmp/lambda.zip

    # 4. S3 Notification
    echo "Configuring S3 Trigger..."
    awslocal s3api put-bucket-notification-configuration \
        --bucket my-bucket \
        --notification-configuration '{
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": "arn:aws:lambda:us-east-1:000000000000:function:ResizeImage",
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": { "Key": { "FilterRules": [{ "Name": "prefix", "Value": "uploads/" }] } }
                }
            ]
        }'
    echo "Lambda and Trigger initialized!"
else
    echo "ERROR: resize_handler.py not found in /etc/localstack/init/ready.d/lambda_code"
    ls -R /etc/localstack/init/ready.d/
fi

echo "All resources initialized successfully!"