# Lambda Python Containerized with Lumigo

A comprehensive example of a containerized Python Lambda function instrumented with Lumigo OpenTelemetry Distribution, demonstrating how to wrap existing AWS service calls with proper instrumentation.

## 🚀 Features

- **Containerized Lambda Deployment**: Uses Docker containers for consistent deployment
- **Lumigo Instrumentation**: Full OpenTelemetry integration with execution tags and programmatic errors
- **Multi-Service Operations**: Demonstrates instrumentation for:
  - **DynamoDB**: CRUD operations with table lifecycle management
  - **S3**: Bucket lifecycle operations (create, upload, list, delete)
  - **HTTP APIs**: External API calls with round-robin endpoint selection
  - **RDS PostgreSQL**: Database operations with user management
- **Structured Logging**: JSON-formatted logs for all operations
- **Error Handling**: Comprehensive error tracking and programmatic error reporting
- **Round-Robin Load Distribution**: Distributes operations across multiple resources

## 📋 Prerequisites

- AWS CLI configured with appropriate permissions
- Docker installed and running
- Python 3.11+
- AWS SSO (optional, for credential management)
- Lumigo account with tracer token

## 🔐 Lumigo Configuration

### Token Management

The deployment scripts support storing your Lumigo tracer token for convenience:

```bash
# Create .lumigo_token file with your token
echo "your_lumigo_tracer_token_here" > .lumigo_token

# The deployment scripts will automatically use this token
./deploy-containerized.sh
```

**Note**: The `.lumigo_token` file is already in `.gitignore` to prevent accidentally committing your token to version control.

## 🏗️ Architecture

### Core Components

- **`lambda_function.py`**: Main Lambda handler with orchestration logic
- **`dynamodb_api.py`**: DynamoDB Data Access Layer (DAL)
- **`s3_api.py`**: S3 Data Access Layer (DAL)
- **`api_calls.py`**: HTTP API Data Access Layer (DAL)
- **`postgresql_api.py`**: RDS PostgreSQL Data Access Layer (DAL)
- **`deploy-containerized.sh`**: Containerized deployment script
- **`deploy-direct.sh`**: Direct ZIP deployment script
- **`create-rds.sh`**: RDS PostgreSQL database creation script
- **`delete-rds.sh`**: RDS PostgreSQL database cleanup script
- **`check-rds-connectivity.sh`**: RDS connectivity troubleshooting script
- **`cleanup-all.sh`**: Comprehensive cleanup of all AWS resources
- **`events/`**: Test event files for Lambda testing

### Database Support

#### DynamoDB
- Automatic table creation if not exists
- Full CRUD operations (Create, Read, Update, Delete)
- Round-robin across 3 tables
- Persistent tables (not automatically deleted)

#### RDS PostgreSQL
- Automatic database setup with `create-rds.sh`
- User management operations (Create, Read, Update, Delete)
- Connection pooling and error handling
- Environment-based configuration

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd lambda-python-containerized
```

### 2. Create RDS PostgreSQL Database (Optional)

```bash
# Make the script executable
chmod +x create-rds.sh

# Create RDS PostgreSQL instance
./create-rds.sh
```

This will create:
- RDS PostgreSQL instance (`db.t3.micro`)
- Security group with PostgreSQL access
- Database subnet group
- Database: `lumigo_test`
- Username: `lumigo_admin`
- Password: `LumigoTest123!`

#### Cleanup RDS Resources

When you're done testing, clean up the RDS resources:

```bash
# Make the cleanup script executable
chmod +x delete-rds.sh

# Delete RDS PostgreSQL instance and associated resources
./delete-rds.sh
```

This will remove:
- RDS PostgreSQL instance
- Security group
- Database subnet group

#### Comprehensive Cleanup

To selectively remove resources created by this project:

```bash
# Make the script executable
chmod +x cleanup-all.sh

# Run interactive cleanup
./cleanup-all.sh
```

The script provides an interactive menu to choose what to clean up:

**Available Options:**
- **Lambda Functions**: `lambda-python-lumigo-direct`, `lambda-python-lumigo-container`
- **CloudWatch Log Groups**: Function logs
- **S3 Buckets**: `example-bucket-*`, `lumigo-test-*`
- **DynamoDB Tables**: `example-table*`
- **RDS PostgreSQL Instance**: `lumigo-test-postgres`
- **ECR Repositories**: `lambda-python-lumigo`
- **IAM Roles and Policies**: Execution roles and attached policies
- **Clean Everything**: All resources at once

**Features:**
- Selective cleanup (choose only what you want to delete)
- Confirmation prompts for each operation
- Automatic AWS SSO credential refresh
- Detailed progress reporting

### 3. Troubleshoot RDS Connectivity (If Needed)

If you encounter RDS connection timeouts:

```bash
# Check RDS connectivity and get troubleshooting guidance
./check-rds-connectivity.sh
```

Common issues and solutions:
- **Lambda not in VPC**: Configure Lambda with VPC settings
- **RDS in private subnet**: Move to public subnet for testing, or use RDS Proxy
- **Security group rules**: Ensure Lambda can access RDS port 5432

### 4. Test Events

The project includes several test events in the `events/` folder:

- **`events/test-event.json`**: All operations enabled (API, S3, DynamoDB, RDS)
- **`events/test-event-rds-only.json`**: RDS operations only
- **`events/local-test.json`**: Simple test for local development

You can also create custom test events with specific `actions` configurations:

```json
{
  "data": "hello world",
  "test": true,
  "actions": {
    "api_operations": true,
    "s3_operations": false,
    "database_operations": true,
    "rds_operations": false
  }
}
```

### 5. Deploy Lambda Function

#### Containerized Deployment (Recommended)

```bash
./deploy-containerized.sh
```

#### Direct ZIP Deployment

```bash
./deploy-direct.sh
```

### 4. Test the Function

The deployment script includes interactive testing options:
- Use default test event
- Use simple test event
- Enter custom JSON event

## 📊 Monitoring and Tracing

### Lumigo Dashboard

All operations are traced with:
- **Execution Tags**: Resource names (tables, buckets, endpoints)
- **Programmatic Errors**: Detailed error tracking
- **Structured Logs**: JSON-formatted operation logs

### CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/lambda-python-lumigo-container --follow

# Check log groups
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/lambda-python-lumigo-container
```

## 🔧 Configuration

### Environment Variables

The Lambda function uses these environment variables:

```bash
OTEL_SERVICE_NAME=lambda-python-lumigo-container
LUMIGO_TRACER_TOKEN=your_lumigo_token
LUMIGO_ENABLE_LOGS=true
DYNAMODB_TABLE_NAME=example-table
S3_BUCKET_NAME=example-bucket
RDS_HOST=your_rds_endpoint
RDS_DATABASE_NAME=lumigo_test
RDS_USERNAME=lumigo_admin
RDS_PASSWORD=LumigoTest123!
```

### IAM Permissions

The Lambda execution role includes:
- `AWSLambdaBasicExecutionRole`: CloudWatch Logs
- `AmazonS3FullAccess`: S3 operations
- `AmazonDynamoDBFullAccess`: DynamoDB operations
- `AmazonRDSFullAccess`: RDS operations

## 📝 API Operations

### DynamoDB Operations

```python
# Example: Wrap existing DynamoDB operations
dal = DynamoDBDAL(table_name)
dal.ensure_table_exists()
dal.create_item(item_data)
dal.read_item(item_id)
dal.update_item(item_id, updates)
dal.delete_item(item_id)
```

### S3 Operations

```python
# Example: Wrap existing S3 operations
dal = S3DAL()
dal.ensure_bucket_exists()
dal.upload_sample_objects()
dal.list_bucket_objects()
dal.delete_bucket_objects()
```

### HTTP API Operations

```python
# Example: Wrap existing API calls
dal = APIDAL()
response = dal.fetch_data(endpoint)
```

### RDS PostgreSQL Operations

```python
# Example: Wrap existing PostgreSQL operations
dal = PostgreSQLDAL()
dal.ensure_table_exists()
dal.create_user(user_data)
dal.read_user(user_id)
dal.update_user(user_id, updates)
dal.delete_user(user_id)
```

## 🔍 Troubleshooting

### Common Issues

1. **RDS Connection Issues**
   - Ensure RDS instance is in "available" status
   - Check security group allows Lambda access
   - Verify environment variables are set

2. **DynamoDB Parameter Validation Errors**
   - The function includes error handling for DynamoDB parameter issues
   - Check CloudWatch logs for detailed error information

3. **S3 Permission Errors**
   - Ensure IAM role has S3 permissions
   - Check bucket names and permissions

### Local Testing

```bash
# Test with local AWS services
./test-local-aws.sh

# Test without AWS services
python lambda_function.py
```

## 📈 Performance

- **Timeout**: 60 seconds (configurable)
- **Memory**: 512MB (configurable)
- **Architecture**: x86_64
- **Runtime**: Python 3.11

## 🔒 Security

- **Encryption**: RDS storage encryption enabled
- **Network**: RDS in private subnets
- **IAM**: Least privilege access
- **Secrets**: Environment variables for sensitive data

## 📚 Additional Resources

- [Lumigo Documentation](https://docs.lumigo.io/)
- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [AWS RDS PostgreSQL](https://docs.aws.amazon.com/rds/latest/userguide/CHAP_PostgreSQL.html)

## 🤝 Contributing

This is an example project demonstrating Lumigo instrumentation patterns. Feel free to adapt and extend for your specific use cases. 