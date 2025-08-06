# Containerized Python Lambda with Lumigo OpenTelemetry Instrumentation

This example demonstrates a containerized AWS Lambda function using Python 3.11 with Lumigo OpenTelemetry instrumentation for distributed tracing.

## Overview

The Lambda function includes:
- Lumigo OpenTelemetry instrumentation using the `@lumigo_wrapped` decorator
- HTTP requests to external APIs (traced)
- AWS SDK operations (S3, DynamoDB - traced)
- **Complete DynamoDB CRUD operations** with detailed logging and execution tags
- Custom business logic
- **Execution Tags** for better trace filtering and identification
- **Programmatic Errors** for custom error categorization
- Error handling and logging

## Prerequisites

- Docker installed and running
- AWS CLI configured with valid credentials
- Lumigo account and tracer token (optional for initial deployment)

## Quick Start (Turnkey Deployment)

For the fastest setup, use the turnkey deployment script:

```bash
# Deploy with Lumigo token
./deploy.sh YOUR_LUMIGO_TOKEN

# Deploy without token (configure later)
./deploy.sh
```

The script will:
- ✅ Check all prerequisites (Docker, AWS CLI, credentials)
- ✅ Create necessary IAM roles automatically
- ✅ Build and push the Docker image
- ✅ Deploy the Lambda function
- ✅ Test the function automatically

**That's it!** Your Lambda function will be running with Lumigo instrumentation.

## Manual Setup Instructions

### 1. Environment Configuration

Environment variables are set with sensible defaults in the Dockerfile. You can override them:

```bash
# Required: Your Lumigo tracer token
export LUMIGO_TRACER_TOKEN="your-lumigo-token-here"

# Optional: Service name for your application
export OTEL_SERVICE_NAME="example-lambda-python"

# Optional: Enable logs (default is false)
export LUMIGO_ENABLE_LOGS="true"
```

### 2. Advanced Deployment

For more control, use the advanced deployment script:

```bash
# Basic deployment
./build-and-deploy.sh <your-account-id> <your-region> <ecr-repo-name>

# With custom Lambda function name
./build-and-deploy.sh <your-account-id> <your-region> <ecr-repo-name> my-custom-function-name
```

**Example:**
```bash
./build-and-deploy.sh 123456789012 us-east-1 lambda-python-lumigo my-lumigo-function
```

#### What the advanced deployment script does:

1. **🔍 Pre-flight Checks:**
   - Verifies Docker is running
   - Validates AWS credentials and account ID
   - Checks for required tools (docker, aws, jq)

2. **🔧 IAM Role Setup:**
   - Creates `lambda-execution-role` if it doesn't exist
   - Attaches necessary policies:
     - `AWSLambdaBasicExecutionRole` (CloudWatch logs)
     - `AmazonS3ReadOnlyAccess` (S3 operations)
     - `AmazonDynamoDBFullAccess` (DynamoDB CRUD operations)

3. **🔍 Environment Variable Validation:**
   - Checks for `LUMIGO_TRACER_TOKEN` (prompts if missing)
   - Validates optional variables (`OTEL_SERVICE_NAME`, `LUMIGO_ENABLE_LOGS`)
   - Sets defaults for missing variables

4. **📦 Build & Deploy:**
   - Builds Docker image
   - Pushes to ECR
   - Creates or updates Lambda function
   - Sets environment variables automatically

5. **🧪 Testing:**
   - Invokes the function with `test-event.json`
   - Displays the response

#### Environment Variables

The script will prompt for or use these environment variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LUMIGO_TRACER_TOKEN` | Your Lumigo tracer token | Yes | Prompted |
| `OTEL_SERVICE_NAME` | Service name | No | `example-lambda-python` |
| `LUMIGO_ENABLE_LOGS` | Enable log instrumentation | No | `true` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | No | `example-table` |
| `S3_BUCKET_NAME` | S3 bucket name | No | `example-bucket` |

### 3. Manual Deployment (Alternative)

If you prefer manual deployment:

```bash
# Build the image
docker build -t lambda-python-lumigo .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag lambda-python-lumigo:latest <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/lambda-python-lumigo:latest

# Push to ECR
docker push <your-account-id>.dkr.ecr.us-east-1.amazonaws.com/lambda-python-lumigo:latest
```

### 4. Test the Function

The deployment script automatically tests the function, or you can test manually:

```bash
aws lambda invoke \
  --function-name <your-function-name> \
  --payload file://test-event.json \
  --cli-binary-format raw-in-base64-out \
  response.json
```

## Lumigo Instrumentation Features

### Automatic Instrumentation

The `@lumigo_wrapped` decorator automatically instruments:
- HTTP requests (requests library)
- AWS SDK operations (boto3)
- Lambda function execution
- Custom spans for business logic

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LUMIGO_TRACER_TOKEN` | Your Lumigo tracer token | Yes |
| `OTEL_SERVICE_NAME` | Service name for your application | No |
| `LUMIGO_ENABLE_LOGS` | Enable log instrumentation | No |
| `LUMIGO_AUTO_TAG` | Auto-extract tags from event (e.g., "user_id,source") | No |

### Advanced Configuration

Additional environment variables you can set:

```bash
# Filter HTTP endpoints (optional)
LUMIGO_FILTER_HTTP_ENDPOINTS_REGEX='["health", "metrics"]'

# Secret masking (optional)
LUMIGO_SECRET_MASKING_REGEX='password|secret|key'

# Disable dependency reporting (optional)
LUMIGO_REPORT_DEPENDENCIES=false

# Auto-extract tags from event (optional)
LUMIGO_AUTO_TAG='user_id,source,request_type'
```

## Execution Tags

The Lambda function demonstrates how to add execution tags for better trace filtering:

### Manual Execution Tags
- **API Call Status**: `api_call_status`, `post_id`
- **S3 Operations**: `s3_bucket_count`, `s3_operation`, `s3_operation_status`
- **DynamoDB CRUD Operations**: 
  - `dynamodb_table` - Table name being accessed
  - `dynamodb_operations` - Types of operations performed (create,read,update,delete)
  - `dynamodb_status` - Overall operation status
  - `dynamodb_item_id` - Item ID being operated on (truncated to 20 chars)
  - `dynamodb_operations_count` - Number of operations completed
  - `dynamodb_create`, `dynamodb_read`, `dynamodb_update`, `dynamodb_delete` - Individual operation status
  - `dynamodb_item_found`, `dynamodb_updated_attrs`, `dynamodb_deleted` - Operation-specific results
- **Business Logic**: `business_logic_result`, `processing_status`
- **Event Data**: `has_data`, `data_length`, `is_test`, `event_source`, `event_timestamp`
- **Error Information**: `error_category`, `error_type`

### Auto Execution Tags
You can configure automatic tag extraction from the Lambda event by setting:
```bash
LUMIGO_AUTO_TAG='user_id,source,request_type'
```

This will automatically extract these fields from the event and create execution tags.

## DynamoDB CRUD Operations

The function performs a complete CRUD (Create, Read, Update, Delete) round trip on DynamoDB:

### Operations Performed
1. **CREATE**: Inserts a new item with unique ID and metadata
2. **READ**: Retrieves the created item to verify it exists
3. **UPDATE**: Updates the item's status and adds an updated_at timestamp
4. **DELETE**: Removes the item from the table

### JSON Logging
Each operation is logged as structured JSON with:
- Operation type and status
- Item ID and response metadata
- Consumed capacity information
- Request IDs for tracing

### Execution Tags
The CRUD operations add comprehensive execution tags:
- `dynamodb_table` - Table name being accessed
- `dynamodb_operations` - Types of operations performed
- `dynamodb_status` - Overall operation status
- `dynamodb_item_id` - Item ID (truncated to stay under 75 chars)
- `dynamodb_operations_count` - Number of operations completed
- Individual operation tags: `dynamodb_create`, `dynamodb_read`, `dynamodb_update`, `dynamodb_delete`
- Result tags: `dynamodb_item_found`, `dynamodb_updated_attrs`, `dynamodb_deleted`

### Error Handling
If any CRUD operation fails:
- Error details are logged as JSON
- Execution tags indicate which operations completed
- Error type and message are captured
- The error is re-raised to trigger programmatic error handling

## Programmatic Errors

The function includes custom error handling with programmatic errors:

### Error Types
- **HTTP_REQUEST_FAILED**: For HTTP request failures
- **LAMBDA_EXECUTION_FAILED**: For general Lambda execution failures

### Error Attributes
Each programmatic error includes:
- Error message and type
- Additional context (URL, error codes, function name, request ID)
- Execution tags for error categorization

## Monitoring in Lumigo

Once deployed, you can monitor your Lambda function in Lumigo:

1. **Traces**: View distributed traces showing the complete request flow
2. **Transactions**: See the transaction graph with all spans
3. **Logs**: View enriched logs with trace context
4. **Metrics**: Monitor performance and error rates

## Troubleshooting

### Common Issues

1. **No traces appearing**: Ensure `LUMIGO_TRACER_TOKEN` is set correctly
2. **Permission errors**: Check IAM roles and permissions
3. **Container build failures**: Verify Dockerfile and requirements.txt

### Debug Mode

For debugging, you can enable span dumping:

```bash
LUMIGO_DEBUG_SPANDUMP=true
```

**Note**: Do not use this in production.

## File Structure

```
.
├── Dockerfile              # Container definition with default env vars
├── lambda_function.py      # Lambda function with Lumigo instrumentation
├── requirements.txt        # Python dependencies
├── deploy.sh              # Turnkey deployment script
├── build-and-deploy.sh    # Advanced deployment script
├── test-event.json        # Sample test event
└── README.md              # This file
```

## Dependencies

- `lumigo_opentelemetry`: Lumigo's OpenTelemetry distribution
- `requests`: HTTP client library
- `boto3`: AWS SDK for Python

## Supported Python Versions

This example uses Python 3.11, which is fully supported by the Lumigo OpenTelemetry Distribution.

## Additional Resources

- [Lumigo OpenTelemetry Distribution Documentation](https://docs.lumigo.io/docs/lumigo-opentelemetry-distribution-for-python)
- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html)
- [Lumigo Dashboard](https://platform.lumigo.io) 