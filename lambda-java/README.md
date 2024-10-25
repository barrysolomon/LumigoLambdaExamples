# Lambda Java Examples with Lumigo Integration

This project contains two AWS Lambda functions:
1. **`LambdaJavaLumigoExampleSimple`** - A simple function that logs messages and returns.
2. **`LambdaJavaLumigoExampleWeather`** - A more complex function that fetches weather data from the OpenWeather API, stores the response in an S3 bucket, and integrates with AWS Secrets Manager.

Both functions are packaged into the same JAR. The user can switch between them by updating the Lambda handler configuration.

## Prerequisites

- **Java 11 or higher**
- **Maven**
- **AWS CLI**
- **AWS Account** with necessary permissions

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/LambdaJavaLumigoExample.git
cd LambdaJavaLumigoExample
```

### 2. Lumigo Configuration

To enable Lumigo logging and tracing:
1. **AWS Tag**: Set an AWS tag `LUMIGO_LOG_COLLECTION` to `true` on the Lambda function.
2. **Environment Variables**:
   - `JAVA_TOOL_OPTIONS`: Set to `'-Djdk.attach.allowAttachSelf=true'`.
   - `LUMIGO_TRACER_TOKEN`: Set to your Lumigo token if it’s not automatically initialized.

### 3. Build the Project

```bash
mvn clean package
```

The packaged JAR file will be located in `target/java-lambda-lumigo-1.0-SNAPSHOT.jar`.

## Deploying the Lambda Function

### 1. Initial Deployment Script

Use the following script to create or update the Lambda function and switch between handlers:

```bash
#!/bin/bash

# Set variables
FUNCTION_NAME="java21lambda"
JAR_PATH="target/java-lambda-lumigo-1.0-SNAPSHOT.jar"
ROLE_ARN="arn:aws:iam::139457818185:role/java21lambda-role-6ntld2sc"  # Replace with your IAM role ARN
REGION="us-east-1"
RUNTIME="java11"
TIMEOUT=30
MEMORY_SIZE=512

# Choose the handler
HANDLER="LambdaJavaLumigoExampleSimple::handleRequest"  # Simple logging function
# Uncomment the following line to use the weather-fetching function
# HANDLER="LambdaJavaLumigoExampleWeather::handleRequest"

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
        --environment Variables="{JAVA_TOOL_OPTIONS='-Djdk.attach.allowAttachSelf=true',LUMIGO_TRACER_TOKEN='your-lumigo-token'}" \
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
        --environment Variables="{JAVA_TOOL_OPTIONS='-Djdk.attach.allowAttachSelf=true',LUMIGO_TRACER_TOKEN='your-lumigo-token'}" \
        --region $REGION
fi

echo "Deployment complete. Handler is set to $HANDLER."
```

### 2. Configure IAM Role and Policies

Add the following permissions to the Lambda role:

```bash
aws iam put-role-policy \
    --role-name java21lambda-role-6ntld2sc \
    --policy-name SecretsManagerAndGlobalS3AccessPolicy \
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
```

### 3. Set Required Tags

Add the `LUMIGO_LOG_COLLECTION` tag to enable Lumigo logging.

```bash
aws lambda tag-resource \
    --resource arn:aws:lambda:us-east-1:139457818185:function:$FUNCTION_NAME \
    --tags LUMIGO_LOG_COLLECTION=true
```

### 4. Create Secrets in AWS Secrets Manager

1. **Navigate to Secrets Manager in AWS Console**.
2. **Create a new secret** for `initech-weather-api-key` and store your API key from OpenWeather.
   - **Secret name**: `initech-weather-api-key`
   - **Secret value**: `{ "key": "your-weather-api-key" }`

## Switching Between Lambda Handlers

The `LambdaJavaLumigoExampleSimple` and `LambdaJavaLumigoExampleWeather` functions are both packaged into the JAR. To switch between them:
1. Update the `HANDLER` variable in the deployment script:
   - **Simple Logging Function**: `LambdaJavaLumigoExampleSimple::handleRequest`
   - **Weather Fetching Function**: `LambdaJavaLumigoExampleWeather::handleRequest`
2. Run the deployment script again.

## Verifying the Deployment

Run a test invocation:

```bash
aws lambda invoke --function-name $FUNCTION_NAME output.json
```

Check `output.json` and CloudWatch logs to verify that the function logs and/or stores the weather data in S3 as expected.

## Troubleshooting

- **Missing Lumigo Tracer**: Ensure `lumigo-tracer.jar` is included in the Lambda layer or accessible at `/opt/lumigo-java/lumigo-tracer.jar`.
- **Environment Variable Issues**: Double-check that `LUMIGO_TRACER_TOKEN` and `JAVA_TOOL_OPTIONS` are correctly set in the Lambda’s environment variables.
- **Secrets Configuration**: Confirm that `initech-weather-api-key` exists in Secrets Manager with the correct permissions and value.

## Additional Notes

- **Memory and Timeout**: Adjust Lambda memory and timeout settings as needed for API response times.
- **Logging and Monitoring**: Check Lumigo's dashboard for enhanced logs and tracing insights.

---