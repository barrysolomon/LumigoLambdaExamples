# Containerized Python Lambda with Lumigo OpenTelemetry

A production-ready example of a containerized Python Lambda function instrumented with Lumigo OpenTelemetry Distribution. This Lambda demonstrates comprehensive AWS service interactions including S3 bucket lifecycle management, DynamoDB CRUD operations (with data preservation), HTTP requests, and structured logging with execution tags.

## 🚀 Features

- **Containerized Lambda**: Uses AWS Lambda Container Images for consistent deployment
- **Lumigo Instrumentation**: Full OpenTelemetry tracing with execution tags and programmatic errors
- **S3 Lifecycle Management**: Create buckets, upload objects, list contents, and cleanup
- **DynamoDB CRUD Operations**: Create, Read, Update operations (DELETE skipped for data preservation)
- **HTTP API Integration**: External API calls with error handling
- **Structured Logging**: JSON-formatted logs with execution context using Python logger
- **Turnkey Deployment**: Automated deployment script with interactive testing
- **Data Preservation**: DynamoDB items are preserved (not deleted) for demonstration purposes

## 📋 Prerequisites

- **AWS CLI** installed and configured
- **Docker** installed and running
- **AWS SSO** or IAM credentials with appropriate permissions
- **Lumigo Account** with tracer token

### Required AWS Permissions

The deployment script will create an IAM role with these policies:
- `AWSLambdaBasicExecutionRole` - CloudWatch Logs
- `AmazonS3FullAccess` - S3 bucket and object operations
- `AmazonDynamoDBFullAccess` - DynamoDB table operations

## 🛠️ Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd lambda-python-containerized
```

### 2. Deploy with Interactive Script

```bash
./deploy.sh
```

The script will:
- ✅ Check prerequisites (Docker, AWS CLI, credentials)
- 🔧 Create IAM role with necessary permissions
- 📦 Build and push Docker image to ECR
- 🚀 Deploy Lambda function with environment variables
- 🧪 Offer interactive testing options

### 3. Test Your Function

The deployment script offers multiple testing options:

```bash
# Option 1: Use default test event
# Option 2: Simple test event
# Option 3: Custom JSON event
# Option 4: Skip testing
```

## 📁 Project Structure

```
lambda-python-containerized/
├── lambda_function.py      # Main Lambda handler with Lumigo instrumentation
├── Dockerfile             # Container image definition
├── requirements.txt       # Python dependencies
├── deploy.sh             # Turnkey deployment script
├── test-event.json       # Sample test event
├── README.md             # This file
└── .gitignore           # Git ignore patterns
```

## 🔧 Configuration

### Environment Variables

The Lambda function uses these environment variables:

| Environment Variable | Description | Default Value |
|---------------------|-------------|---------------|
| `OTEL_SERVICE_NAME` | Service name for tracing | `lambda-python-lumigo-container` |
| `LUMIGO_TRACER_TOKEN` | Your Lumigo tracer token | `t_f8f7b905da964eef89261` |
| `LUMIGO_ENABLE_LOGS` | Enable Lumigo logging | `true` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | `example-table` |
| `S3_BUCKET_NAME` | S3 bucket name | `example-bucket` |

### Lumigo Configuration

The function is instrumented with Lumigo OpenTelemetry Distribution:

```python
from lumigo_opentelemetry import lumigo_wrapped

@lumigo_wrapped
def lambda_handler(event, context):
    # Your Lambda code here
```

## 🎯 Function Capabilities

### 1. S3 Bucket Lifecycle Management
- **Round-robin** through 3 buckets: `example-bucket`, `example-bucket-2`, `example-bucket-3`
- **Create bucket** if it doesn't exist
- **Upload sample objects** with metadata
- **List bucket contents** with detailed logging
- **Delete objects** for cleanup (buckets remain)

### 2. DynamoDB CRUD Operations
- **Round-robin** through 3 tables: `example-table`, `example-table-2`, `example-table-3`
- **Create table** if it doesn't exist
- **CREATE**: Insert new items with UUID
- **READ**: Retrieve items by ID
- **UPDATE**: Modify item attributes
- **DELETE**: **SKIPPED** for data preservation (items remain in table)

### 3. HTTP API Integration
- **Round-robin** through 3 endpoints:
  - `https://jsonplaceholder.typicode.com/posts/1`
  - `https://jsonplaceholder.typicode.com/posts/2`
  - `https://jsonplaceholder.typicode.com/posts/3`
- **Error handling** with programmatic errors
- **Response logging** with timing information

### 4. Structured Logging
- **Python logger** instead of print statements
- **JSON-formatted logs** with Data_Source, Data_Target, Data_Artifacts
- **Safe serialization** for datetime objects and complex data structures
- **Execution tags** for resource identification
- **Programmatic errors** for error categorization

## 📊 Monitoring and Observability

### Lumigo Dashboard
- **Traces**: View complete request flows
- **Execution Tags**: Filter by table names, bucket names, API endpoints
- **Errors**: Programmatic error categorization
- **Performance**: Response times and operation metrics

### CloudWatch Logs
- **Structured JSON logs** for easy parsing
- **Operation details** with metadata
- **Error tracking** with stack traces

### Execution Tags
The function automatically adds these execution tags:
- `api_endpoint` - HTTP endpoint used
- `s3_bucket` - S3 bucket name
- `dynamodb_table` - DynamoDB table name
- `user_id` - From event payload (if present)
- `source` - From event payload (if present)

## 🧪 Testing

### Supported Event Payloads

#### Basic Event (Default)
```json
{
  "data": "hello world from lumigo",
  "test": true,
  "timestamp": "2024-01-01T00:00:00Z",
  "source": "test",
  "user_id": "user123",
  "request_type": "api_call"
}
```

#### Minimal Event
```json
{
  "test": true
}
```

#### Empty Event
```json
{}
```

#### Custom Data Processing
```json
{
  "data": "custom message to process",
  "user_id": "user456",
  "source": "api_gateway"
}
```

### Manual Testing

You can also test the function manually using AWS CLI:

```bash
# Test with default event
aws lambda invoke --function-name lambda-python-lumigo-container --payload '{"data": "test message"}' response.json

# Test with empty event
aws lambda invoke --function-name lambda-python-lumigo-container --payload '{}' response.json

# Test with custom event
aws lambda invoke --function-name lambda-python-lumigo-container --payload '{"user_id": "user789", "source": "manual_test"}' response.json
```

### Troubleshooting

#### View Logs
```bash
# View CloudWatch logs
aws logs tail /aws/lambda/lambda-python-lumigo-container --follow

# Get function details
aws lambda get-function --function-name lambda-python-lumigo-container

# Get function configuration
aws lambda get-function-configuration --function-name lambda-python-lumigo-container
```

## 🚀 Performance

### Optimizations
- **Container image** optimized for Lambda cold starts
- **Structured logging** reduces parsing overhead
- **Safe JSON serialization** prevents serialization errors
- **Round-robin distribution** spreads load across resources

### Resource Usage
- **Memory**: 512 MB (configurable)
- **Timeout**: 30 seconds (configurable)
- **Architecture**: x86_64 for Mac compatibility

## 🔒 Security

### Best Practices
- **Environment variables** for sensitive configuration
- **IAM roles** with minimal required permissions
- **Container images** from trusted sources
- **Structured logging** without sensitive data exposure

### Data Handling
- **DynamoDB items** are preserved (not deleted)
- **S3 objects** are cleaned up after operations
- **No sensitive data** logged in structured logs

## 🏭 Production Deployment

### Pre-deployment Checklist
- [ ] Update `LUMIGO_TRACER_TOKEN` with production token
- [ ] Review IAM permissions for production environment
- [ ] Test with production-like event payloads
- [ ] Verify CloudWatch log retention settings
- [ ] Set up monitoring alerts

### Environment-Specific Configuration
```bash
# Production deployment
export LUMIGO_TRACER_TOKEN="your_production_token"
export OTEL_SERVICE_NAME="production-lambda-python-lumigo"
./deploy.sh
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
- **Lumigo Documentation**: [https://docs.lumigo.io](https://docs.lumigo.io)
- **AWS Lambda Documentation**: [https://docs.aws.amazon.com/lambda/](https://docs.aws.amazon.com/lambda/)
- **OpenTelemetry Documentation**: [https://opentelemetry.io/docs/](https://opentelemetry.io/docs/)

---

**Note**: This Lambda function is designed for demonstration and learning purposes. For production use, ensure proper security, monitoring, and error handling are implemented according to your organization's standards. 