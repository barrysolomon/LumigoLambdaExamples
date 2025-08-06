#!/bin/bash

# Build and Deploy Script for Containerized Python Lambda with Lumigo
# Usage: ./build-and-deploy.sh <aws-account-id> <aws-region> <ecr-repository-name> [lambda-function-name]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if required arguments are provided
if [ $# -lt 3 ] || [ $# -gt 4 ]; then
    echo "Usage: $0 <aws-account-id> <aws-region> <ecr-repository-name> [lambda-function-name]"
    echo "Example: $0 123456789012 us-east-1 lambda-python-lumigo my-lambda-function"
    exit 1
fi

AWS_ACCOUNT_ID=$1
AWS_REGION=$2
ECR_REPOSITORY_NAME=$3
LAMBDA_FUNCTION_NAME=${4:-"lambda-python-lumigo-function"}
IMAGE_TAG="latest"

echo -e "${BLUE}🚀 Starting build and deployment process...${NC}"
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo "ECR Repository: $ECR_REPOSITORY_NAME"
echo "Lambda Function Name: $LAMBDA_FUNCTION_NAME"

# Function to check command existence
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed. Please install it first.${NC}"
        exit 1
    fi
}

# Function to check AWS credentials
check_aws_credentials() {
    echo -e "${BLUE}🔍 Checking AWS credentials...${NC}"
    
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  AWS CLI is not configured or credentials are invalid.${NC}"
        echo "Please run 'aws configure' to set up your credentials."
        echo "Or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_DEFAULT_REGION environment variables."
        exit 1
    fi
    
    # Get current AWS identity
    CALLER_IDENTITY=$(aws sts get-caller-identity --output json)
    USER_ARN=$(echo $CALLER_IDENTITY | jq -r '.Arn')
    ACCOUNT_ID=$(echo $CALLER_IDENTITY | jq -r '.Account')
    
    echo -e "${GREEN}✅ AWS credentials are valid${NC}"
    echo "User ARN: $USER_ARN"
    echo "Account ID: $ACCOUNT_ID"
    
    # Verify account ID matches
    if [ "$ACCOUNT_ID" != "$AWS_ACCOUNT_ID" ]; then
        echo -e "${YELLOW}⚠️  Warning: AWS account ID ($ACCOUNT_ID) doesn't match provided account ID ($AWS_ACCOUNT_ID)${NC}"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to check and create IAM roles
setup_iam_roles() {
    echo -e "${BLUE}🔧 Setting up IAM roles...${NC}"
    
    # Check if Lambda execution role exists
    EXECUTION_ROLE_NAME="lambda-execution-role"
    
    if ! aws iam get-role --role-name $EXECUTION_ROLE_NAME > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Lambda execution role '$EXECUTION_ROLE_NAME' not found.${NC}"
        echo "Creating IAM role for Lambda execution..."
        
        # Create trust policy for Lambda
        cat > /tmp/trust-policy.json << EOF
{
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
}
EOF
        
        # Create the role
        aws iam create-role \
            --role-name $EXECUTION_ROLE_NAME \
            --assume-role-policy-document file:///tmp/trust-policy.json \
            --description "Execution role for Lambda function with Lumigo instrumentation"
        
        echo -e "${GREEN}✅ Created IAM role: $EXECUTION_ROLE_NAME${NC}"
    else
        echo -e "${GREEN}✅ IAM role '$EXECUTION_ROLE_NAME' already exists${NC}"
    fi
    
    # Attach necessary policies
    echo "Attaching policies to IAM role..."
    
    # Basic Lambda execution policy
    aws iam attach-role-policy \
        --role-name $EXECUTION_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # S3 access policy
    aws iam attach-role-policy \
        --role-name $EXECUTION_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
    
    # DynamoDB access policy
    aws iam attach-role-policy \
        --role-name $EXECUTION_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
    
    echo -e "${GREEN}✅ IAM role policies attached${NC}"
}

# Function to check environment variables
check_environment_variables() {
    echo -e "${BLUE}🔍 Checking environment variables...${NC}"
    
    # Check Lumigo token
    if [ -z "$LUMIGO_TRACER_TOKEN" ]; then
        echo -e "${YELLOW}⚠️  LUMIGO_TRACER_TOKEN environment variable is not set.${NC}"
        echo "You can set it now or configure it later in the Lambda function."
        read -p "Enter your Lumigo tracer token (or press Enter to skip): " LUMIGO_TOKEN_INPUT
        
        if [ ! -z "$LUMIGO_TOKEN_INPUT" ]; then
            export LUMIGO_TRACER_TOKEN="$LUMIGO_TOKEN_INPUT"
            echo -e "${GREEN}✅ LUMIGO_TRACER_TOKEN set${NC}"
        else
            echo -e "${YELLOW}⚠️  Remember to set LUMIGO_TRACER_TOKEN in your Lambda function environment variables${NC}"
        fi
    else
        echo -e "${GREEN}✅ LUMIGO_TRACER_TOKEN is set${NC}"
    fi
    
    # Check other optional environment variables
    if [ -z "$OTEL_SERVICE_NAME" ]; then
        echo -e "${BLUE}ℹ️  OTEL_SERVICE_NAME not set, will use default${NC}"
    else
        echo -e "${GREEN}✅ OTEL_SERVICE_NAME is set: $OTEL_SERVICE_NAME${NC}"
    fi
    
    if [ -z "$LUMIGO_ENABLE_LOGS" ]; then
        echo -e "${BLUE}ℹ️  LUMIGO_ENABLE_LOGS not set, will use default (false)${NC}"
    else
        echo -e "${GREEN}✅ LUMIGO_ENABLE_LOGS is set: $LUMIGO_ENABLE_LOGS${NC}"
    fi
}

# Function to check Docker
check_docker() {
    echo -e "${BLUE}🔍 Checking Docker...${NC}"
    
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Docker is running${NC}"
}

# Function to build and push Docker image
build_and_push_image() {
    echo -e "${BLUE}📦 Building Docker image...${NC}"
    docker build -t $ECR_REPOSITORY_NAME:$IMAGE_TAG .
    
    echo -e "${BLUE}🔐 Logging into ECR...${NC}"
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    echo -e "${BLUE}🏷️  Tagging image for ECR...${NC}"
    docker tag $ECR_REPOSITORY_NAME:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:$IMAGE_TAG
    
    echo -e "${BLUE}📤 Pushing image to ECR...${NC}"
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:$IMAGE_TAG
    
    echo -e "${GREEN}✅ Docker image built and pushed successfully${NC}"
}

# Function to create or update Lambda function
deploy_lambda_function() {
    echo -e "${BLUE}🚀 Deploying Lambda function...${NC}"
    
    IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:$IMAGE_TAG"
    EXECUTION_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/lambda-execution-role"
    
    # Check if function exists
    if aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Lambda function '$LAMBDA_FUNCTION_NAME' already exists. Updating...${NC}"
        
        # Update function code
        aws lambda update-function-code \
            --function-name $LAMBDA_FUNCTION_NAME \
            --image-uri $IMAGE_URI
        
        # Update function configuration
        aws lambda update-function-configuration \
            --function-name $LAMBDA_FUNCTION_NAME \
            --environment Variables="{
                LUMIGO_TRACER_TOKEN=$LUMIGO_TRACER_TOKEN,
                OTEL_SERVICE_NAME=${OTEL_SERVICE_NAME:-example-lambda-python},
                LUMIGO_ENABLE_LOGS=${LUMIGO_ENABLE_LOGS:-true},
                DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-example-table},
                S3_BUCKET_NAME=${S3_BUCKET_NAME:-example-bucket}
            }" \
            --timeout 30 \
            --memory-size 512
        
        echo -e "${GREEN}✅ Lambda function updated successfully${NC}"
    else
        echo -e "${BLUE}📝 Creating new Lambda function...${NC}"
        
        # Create function
        aws lambda create-function \
            --function-name $LAMBDA_FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$IMAGE_URI \
            --role $EXECUTION_ROLE_ARN \
            --environment Variables="{
                LUMIGO_TRACER_TOKEN=$LUMIGO_TRACER_TOKEN,
                OTEL_SERVICE_NAME=${OTEL_SERVICE_NAME:-example-lambda-python},
                LUMIGO_ENABLE_LOGS=${LUMIGO_ENABLE_LOGS:-true},
                DYNAMODB_TABLE_NAME=${DYNAMODB_TABLE_NAME:-example-table},
                S3_BUCKET_NAME=${S3_BUCKET_NAME:-example-bucket}
            }" \
            --timeout 30 \
            --memory-size 512
        
        echo -e "${GREEN}✅ Lambda function created successfully${NC}"
    fi
}

# Function to test the Lambda function
test_lambda_function() {
    echo -e "${BLUE}🧪 Testing Lambda function...${NC}"
    
    if [ -f "test-event.json" ]; then
        echo "Invoking Lambda function with test event..."
        aws lambda invoke \
            --function-name $LAMBDA_FUNCTION_NAME \
            --payload file://test-event.json \
            --cli-binary-format raw-in-base64-out \
            response.json
        
        echo -e "${GREEN}✅ Lambda function invoked successfully${NC}"
        echo "Response saved to response.json"
        
        # Display response
        if [ -f "response.json" ]; then
            echo -e "${BLUE}📄 Function response:${NC}"
            cat response.json | jq '.' 2>/dev/null || cat response.json
        fi
    else
        echo -e "${YELLOW}⚠️  test-event.json not found, skipping test${NC}"
    fi
}

# Main execution
main() {
    # Check required commands
    check_command "docker"
    check_command "aws"
    check_command "jq"
    
    # Run checks and setup
    check_aws_credentials
    check_environment_variables
    check_docker
    setup_iam_roles
    
    # Build and deploy
    build_and_push_image
    deploy_lambda_function
    test_lambda_function
    
    echo ""
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📋 Summary:${NC}"
    echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
    echo "Image URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY_NAME:$IMAGE_TAG"
    echo "Region: $AWS_REGION"
    echo ""
    echo -e "${BLUE}🔗 Next steps:${NC}"
    echo "1. Monitor your function in the AWS Lambda console"
    echo "2. View traces in the Lumigo dashboard"
    echo "3. Check CloudWatch logs for detailed execution logs"
    echo "4. Test with different events using: aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME --payload '{\"test\": true}' response.json"
}

# Run main function
main 