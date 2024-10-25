# LambdaJavaLumigoExamples

This Lambda function fetches weather data from the OpenWeather API, stores the response in an S3 bucket, and integrates with Lumigo for distributed tracing and enhanced logging. Follow these instructions to set up, build, and deploy this Lambda function.

## Prerequisites

- **Java 11 or higher**: Ensure Java is installed and available in your PATH.
- **Maven**: Used for building and packaging the Java project.
- **AWS CLI**: Used for deploying the Lambda function and managing AWS resources.
- **AWS Account**: Required permissions for Secrets Manager, S3, CloudWatch Logs, and Lambda.

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/barrysolomon/LumigoLambdaExamples.git
cd LambdaJavaLumigoExample
```

### 2. Project Structure

- **src/main/java**: Java source files.
- **src/main/resources**: Any additional resources.
- **pom.xml**: Maven configuration and dependencies.

### 3. Configuration for Lumigo Tracing

To enable Lumigo logging and tracing:

1. **AWS Tag**: Add an AWS tag `LUMIGO_LOG_COLLECTION` set to `true` to enable Lumigo’s log collection.
2. **Environment Variables**:
   - `JAVA_TOOL_OPTIONS`: Set to `'-Djdk.attach.allowAttachSelf=true'` to allow Lumigo’s tracer agent to attach.
   - `LUMIGO_TRACER_TOKEN`: Set this environment variable with the Lumigo tracer token if it’s not automatically set during logging initialization.

### 4. Dependencies

Add the necessary dependencies in `pom.xml` for AWS SDK, S3, Secrets Manager, Lumigo, and any other required libraries.

#### Sample Dependency Configuration

Ensure `pom.xml` includes:

```xml
<dependencies>
    <!-- AWS SDK for Lambda, S3, and Secrets Manager -->
    <dependency>
        <groupId>com.amazonaws</groupId>
        <artifactId>aws-java-sdk-lambda</artifactId>
        <version>1.12.506</version>
    </dependency>
    <dependency>
        <groupId>com.amazonaws</groupId>
        <artifactId>aws-java-sdk-s3</artifactId>
        <version>1.12.506</version>
    </dependency>
    <dependency>
        <groupId>com.amazonaws</groupId>
        <artifactId>aws-java-sdk-secretsmanager</artifactId>
        <version>1.12.506</version>
    </dependency>

    <!-- Lumigo SDK -->
    <dependency>
        <groupId>io.lumigo</groupId>
        <artifactId>lumigo-agent</artifactId>
        <version>1.0.0</version>
    </dependency>
</dependencies>
```

## Building and Packaging the Lambda Function

1. **Build the Project**:

   ```bash
   mvn clean package
   ```

2. **Output Jar**: The packaged JAR file is located at `target/java-lambda-lumigo-1.0-SNAPSHOT.jar`.

## Creating and Deploying the Lambda Function

### 1. Create the Lambda Function

Use the following script to create or update the Lambda function.

```bash
#!/bin/bash

# Set variables
FUNCTION_NAME="java21lambda"
JAR_PATH="target/java-lambda-lumigo-1.0-SNAPSHOT.jar"
HANDLER="LambdaJavaLumigoExampleSimple::handleRequest"  # Replace with your actual handler
ROLE_ARN="arn:aws:iam::139457818185:role/java21lambda-role-6ntld2sc"  # Replace with your IAM role ARN
REGION="us-east-1"
RUNTIME="java11"
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

echo "Deployment complete."
```

### 2. Add Necessary AWS Policies

Ensure the Lambda function has the required permissions to access S3, Secrets Manager, and CloudWatch Logs. Use the following AWS CLI commands:

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

Ensure the following tag is set on your Lambda function:

- **Key**: `LUMIGO_LOG_COLLECTION`
- **Value**: `true`

This tag enables Lumigo’s log collection on your Lambda function. You can set tags with the following command:

```bash
aws lambda tag-resource \
    --resource arn:aws:lambda:us-east-1:139457818185:function:$FUNCTION_NAME \
    --tags LUMIGO_LOG_COLLECTION=true
```

### 4. Verify and Test

Run a test invocation of the Lambda function:

```bash
aws lambda invoke --function-name $FUNCTION_NAME output.json
```

Check `output.json` and CloudWatch logs for expected logs and behavior.

## Troubleshooting

1. **Missing Lumigo Tracer**: If you encounter errors related to the Lumigo tracer jar file, verify that the Lumigo layer is attached to the Lambda and that the path `/opt/lumigo-java/lumigo-tracer.jar` exists.
2. **Environment Variable Issues**: Confirm that `LUMIGO_TRACER_TOKEN` and `JAVA_TOOL_OPTIONS` are correctly set in the Lambda’s environment variables.
3. **Permission Errors**: Double-check that the Lambda role has the necessary permissions as per the attached IAM policy.

## Additional Notes

- **Logging Configuration**: Lumigo’s tracer provides enhanced logs and distributed tracing. Ensure your function’s logs and traces appear as expected in Lumigo’s dashboard.
- **Memory and Timeout Settings**: Adjust memory and timeout values based on the expected workload and response time from external services like OpenWeather.

---