#!/bin/bash

# Set variables
FUNCTION_NAME="java21lambda"
JAR_PATH="target/java-lambda-lumigo-1.0-SNAPSHOT.jar"
HANDLER="LambdaJavaLumigoExampleSimple::handleRequest" # Replace with your actual handler
ROLE_NAME="java21lambda-role-6ntld2sc"
REGION="us-east-1"
RUNTIME="java17"
TIMEOUT=30
MEMORY_SIZE=512

# Policy names
POLICY_NAME="SecretsManagerAndS3AccessPolicy"

# Create the IAM role if it doesn't exist
echo "Checking if IAM role $ROLE_NAME exists..."

aws iam get-role --role-name $ROLE_NAME >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Creating IAM role: $ROLE_NAME"
    
    # Create the role with a trust relationship allowing Lambda to assume it
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }'
    
    echo "Attaching policies to role: $ROLE_NAME"

    # Attach policies for S3, Secrets Manager, and CloudWatch Logs access
    aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name $POLICY_NAME \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "secretsmanager:GetSecretValue",
                    "Resource": [
                        "arn:aws:secretsmanager:us-east-1:139457818185:secret:initech-lumigo-token*",
                        "arn:aws:secretsmanager:us-east-1:139457818185:secret:initech-weather-api-key*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "arn:aws:logs:us-east-1:139457818185:log-group:/aws/lambda/$FUNCTION_NAME:*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:CreateBucket",
                        "s3:PutObject",
                        "s3:ListBucket",
                        "s3:ListAllMyBuckets"
                    ],
                    "Resource": "*"
                }
            ]
        }'
else
    echo "IAM role $ROLE_NAME already exists."
fi

# Check if the Lambda function exists
echo "Checking if Lambda function $FUNCTION_NAME exists..."
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Creating Lambda function: $FUNCTION_NAME"
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role arn:aws:iam::139457818185:role/$ROLE_NAME \
        --handler $HANDLER \
        --zip-file fileb://$JAR_PATH \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --region $REGION
else
    echo "Updating Lambda function: $FUNCTION_NAME"
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://$JAR_PATH \
        --region $REGION

    sleep 2
    echo "Updating Lambda function configuration: $FUNCTION_NAME"

    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --handler $HANDLER \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --region $REGION

    sleep 2
fi

echo "Deployment complete."
