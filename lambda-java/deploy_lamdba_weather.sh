#!/bin/bash

# Set variables
FUNCTION_NAME="java21lambda"
JAR_PATH="target/java-lambda-lumigo-1.0-SNAPSHOT.jar"
HANDLER="LambdaJavaLumigoExampleWeather::handleRequest"                     # Replace with your actual handler
ROLE_ARN="arn:aws:iam::139457818185:role/java21lambda-role-6ntld2sc" # Replace with your IAM role ARN
REGION="us-east-1"
RUNTIME="java17" # Updated to java11
TIMEOUT=30
MEMORY_SIZE=512

# Policy names
POLICY_NAME="SecretsManagerAndS3AccessPolicy"

# Check if the Lambda function exists
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION >/dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Creating Lambda function: $FUNCTION_NAME"
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
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

    sleep 5

    echo "Updating Lambda function Configuration: $FUNCTION_NAME"

    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --handler $HANDLER \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --region $REGION

    sleep 2

fi

# Add permissions for Secrets Manager, CloudWatch Logs, and S3 to the Lambda role
echo "Attaching necessary policies to the role: $ROLE_ARN"

# Create inline policy document
POLICY_DOCUMENT='{
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
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::my-weather-data-bucket",
                "arn:aws:s3:::my-weather-data-bucket/*"
            ]
        }
    ]
}'

# Apply the inline policy
aws iam put-role-policy \
    --role-name $(basename $ROLE_ARN) \
    --policy-name $POLICY_NAME \
    --policy-document "$POLICY_DOCUMENT"

echo "Deployment complete with updated permissions."
