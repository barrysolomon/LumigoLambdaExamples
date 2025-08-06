# Lambda Python Containerized with Lumigo OpenTelemetry

A containerized Python Lambda function demonstrating AWS service integration with Lumigo OpenTelemetry tracing, structured JSON logging, and execution tags.

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured
- Docker installed
- Lumigo account with tracer token

### Deploy
```bash
# Set your Lumigo token
echo "your_lumigo_token_here" > .lumigo_token

# Deploy containerized Lambda
./deploy-containerized.sh

# Or deploy as ZIP package
./deploy-direct.sh
```

## 📊 Features

### **AWS Service Integration**
- **DynamoDB**: CRUD operations with table lifecycle management
- **S3**: Bucket lifecycle (upload, list, delete objects)
- **HTTP APIs**: External API calls with round-robin endpoints

### **Lumigo Instrumentation**
- **OpenTelemetry Distribution**: `lumigo-opentelemetry`
- **Execution Tags**: Automatic tagging of resources
- **Structured JSON Logging**: Rich, parseable logs
- **Programmatic Errors**: Error categorization

### **Deployment Options**
- **Containerized**: Docker-based with ECR
- **Direct ZIP**: Traditional Lambda package

## 🔧 Configuration

### Environment Variables
```bash
LUMIGO_TRACER_TOKEN=your_token
OTEL_SERVICE_NAME=lambda-python-lumigo-container
LUMIGO_ENABLE_LOGS=true
DYNAMODB_TABLE_NAME=example-table
S3_BUCKET_NAME=example-bucket
```

### IAM Permissions
- CloudWatch Logs
- DynamoDB full access
- S3 full access

## 📈 Monitoring

### **Lumigo Dashboard**
- Complete request traces
- Execution tag filtering
- Error categorization
- Performance metrics

### **CloudWatch Logs**
- Structured JSON logs
- Service operation details
- Error context

## 🧪 Testing

### Test Events
```json
{
  "data": "hello world from lumigo",
  "test": true,
  "user_id": "user123"
}
```

### Round-Robin Testing
- **DynamoDB**: 3 different tables
- **S3**: 3 different buckets  
- **API**: 3 different endpoints

## 📁 Project Structure
```
├── lambda_function.py      # Main handler with orchestration
├── dynamodb_api.py        # DynamoDB Data Access Layer
├── s3_api.py             # S3 Data Access Layer
├── api_calls.py          # HTTP API Data Access Layer
├── deploy-containerized.sh # Containerized deployment
├── deploy-direct.sh      # Direct ZIP deployment
└── test-event.json      # Sample test event
```

## 🚨 Troubleshooting

### Common Issues
- **DynamoDB Parameter Errors**: Check item format
- **S3 Access Denied**: Verify IAM permissions
- **Container Build Failures**: Ensure Docker is running
- **Lambda Timeout**: Increase timeout (currently 60s)

### Debug Commands
```bash
# View logs
aws logs tail /aws/lambda/lambda-python-lumigo-container --follow

# Test function
aws lambda invoke --function-name lambda-python-lumigo-container --payload file://test-event.json response.json
```

## 📚 API Reference

### Execution Tags
```python
add_execution_tag("database", "DynamoDB")
add_execution_tag("database_table", "example-table")
add_execution_tag("s3_bucket", "example-bucket")
add_execution_tag("api_url", "https://api.example.com")
```

### Programmatic Errors
```python
add_programmatic_error("SERVICE_ERROR", "Error message")
```

## 🔗 Resources
- [Lumigo Documentation](https://docs.lumigo.io)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python)

---

**Note**: This is a demonstration project showing best practices for instrumenting Python Lambda functions with Lumigo OpenTelemetry. 