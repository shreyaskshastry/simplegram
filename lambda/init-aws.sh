#!/bin/bash
# 1. Infrastructure
awslocal s3 mb s3://my-bucket
awslocal dynamodb create-table --table-name Images --attribute-definitions AttributeName=ImageId,AttributeType=S --key-schema AttributeName=ImageId,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
awslocal dynamodb create-table --table-name Logs --attribute-definitions AttributeName=LogId,AttributeType=S --key-schema AttributeName=LogId,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
awslocal dynamodb create-table --table-name Stats --attribute-definitions AttributeName=StatName,AttributeType=S --key-schema AttributeName=StatName,KeyType=HASH --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5

# 2. Stats Init
awslocal dynamodb put-item --table-name Stats --item '{"StatName": {"S": "uploads"}, "Value": {"N": "0"}}'
awslocal dynamodb put-item --table-name Stats --item '{"StatName": {"S": "downloads"}, "Value": {"N": "0"}}'
awslocal dynamodb put-item --table-name Stats --item '{"StatName": {"S": "deletes"}, "Value": {"N": "0"}}'

# 3. Lambda Setup
cd /etc/localstack/init/ready.d/lambda_dist
zip -r ../lambda.zip .
cd ..

awslocal lambda create-function \
    --function-name ResizeImage \
    --runtime python3.11 \
    --handler resize_handler.handler \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --zip-file fileb://lambda.zip

# 4. S3 Notification
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

echo "AWS Local Resources Initialized!"