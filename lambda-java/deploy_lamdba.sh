#!/bin/bash

# Set variables
FUNCTION_NAME="java21lambda"
JAR_PATH="target/java-lambda-lumigo-1.0-SNAPSHOT.jar"
HANDLER="LambdaJavaLumigoExample::handleRequest"  # Replace with your actual handler
ROLE_ARN="arn:aws:iam::139457818185:role/java21lambda-role-6ntld2sc"  # Replace with your IAM role ARN
REGION="us-east-1"
RUNTIME="java21"  # Use the appropriate runtime, e.g., java11, java8.al2
TIMEOUT=30
MEMORY_SIZE=512

# Check if the Lambda function exists
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1

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

    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --handler $HANDLER \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --region $REGION
fi

echo "Deployment complete."
