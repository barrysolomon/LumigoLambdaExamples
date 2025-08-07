#!/bin/bash

# Turnkey Deployment Script for Containerized Python Lambda with Lumigo
# Usage: ./deploy.sh [lumigo-token]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="lambda-python-lumigo-container"
REGION="us-east-1"
ECR_REPOSITORY="lambda-python-lumigo"
IMAGE_TAG="latest"
ROLE_NAME="lambda-execution-role"

# Initialize AWS account ID (will be set properly later)
AWS_ACCOUNT_ID=""

echo -e "${BLUE}🚀 Turnkey Lambda Deployment with Lumigo${NC}"
echo "================================================"

# Function to check if Lambda function exists
check_lambda_exists() {
    if aws lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to run existing Lambda function
run_existing_lambda() {
    echo -e "${BLUE}🧪 Running existing Lambda function...${NC}"
    test_function_interactive
    
    echo ""
    echo -e "${GREEN}🎉 Testing completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📋 Summary:${NC}"
    echo "Function Name: $FUNCTION_NAME"
    echo "Region: $REGION"
    echo ""
    echo -e "${BLUE}🔗 Next steps:${NC}"
    echo "1. View function in AWS Lambda console"
    echo "2. Check CloudWatch logs for execution details"
    echo "3. Monitor traces in Lumigo dashboard"
}

# Function to build and deploy Lambda function
build_and_deploy_lambda() {
    echo -e "${BLUE}🔨 Building and deploying Lambda function...${NC}"
    
    # Check prerequisites
    check_prerequisites
    
    # Get AWS account ID
    get_aws_account_id
    
    # Setup Lumigo token
    setup_lumigo_token
    
    # Setup IAM role
    setup_iam_role
    
    # Build and push Docker image
    build_and_push
    
    # Deploy Lambda function
    deploy_lambda
    
    # Test the function
    test_function_interactive
    
    echo ""
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📋 Summary:${NC}"
    echo "Function Name: $FUNCTION_NAME"
    echo "Region: $REGION"
    echo "Image: $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:latest"
    echo ""
    echo -e "${BLUE}🔗 Next steps:${NC}"
    echo "1. View function in AWS Lambda console"
    if [ ! -z "$LUMIGO_TOKEN" ]; then
        echo "2. Monitor traces in Lumigo dashboard"
    else
        echo "2. Set LUMIGO_TRACER_TOKEN in Lambda environment variables to enable tracing"
    fi
    echo "3. Check CloudWatch logs for execution details"
}

# Initial prompt for user choice
initial_prompt() {
    while true; do
        if check_lambda_exists; then
            echo -e "${GREEN}✅ Lambda function '$FUNCTION_NAME' exists${NC}"
            echo ""
            echo "What would you like to do?"
            echo "1. 🧪 Run existing Lambda function (test without rebuilding)"
            echo "2. 🔨 Build and deploy Lambda function (rebuild and redeploy)"
            echo "3. ❌ Exit"
            echo ""
            read -p "Choose an option (1-3): " -n 1 -r
            echo
            echo ""
            
            if [[ $REPLY =~ ^[1]$ ]]; then
                run_existing_lambda
                echo ""
                echo -e "${BLUE}🔄 Returning to main menu...${NC}"
                echo ""
            elif [[ $REPLY =~ ^[2]$ ]]; then
                build_and_deploy_lambda
                echo ""
                echo -e "${BLUE}🔄 Returning to main menu...${NC}"
                echo ""
            else
                echo "Exiting. Goodbye!"
                exit 0
            fi
        else
            echo -e "${YELLOW}⚠️  Lambda function '$FUNCTION_NAME' does not exist${NC}"
            echo ""
            echo "What would you like to do?"
            echo "1. 🔨 Build and deploy Lambda function (create new function)"
            echo "2. ❌ Exit"
            echo ""
            read -p "Choose an option (1-2): " -n 1 -r
            echo
            echo ""
            
            if [[ $REPLY =~ ^[1]$ ]]; then
                build_and_deploy_lambda
                echo ""
                echo -e "${BLUE}🔄 Returning to main menu...${NC}"
                echo ""
            else
                echo "Exiting. Goodbye!"
                exit 0
            fi
        fi
    done
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running. Please start Docker and try again.${NC}"
        exit 1
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}❌ AWS CLI is not installed. Please install AWS CLI first.${NC}"
        exit 1
    fi
    
    # Check and refresh AWS credentials
    refresh_aws_credentials
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to refresh AWS credentials
refresh_aws_credentials() {
    echo -e "${BLUE}🔄 Checking AWS credentials...${NC}"
    
    # Try to get caller identity to test credentials
    if ! aws sts get-caller-identity --query Account --output text > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  AWS credentials appear to be expired or invalid${NC}"
        
        # Try AWS SSO login directly
        echo -e "${BLUE}🔄 Attempting AWS SSO login...${NC}"
        if aws sso login; then
            echo -e "${GREEN}✅ AWS SSO credentials refreshed successfully${NC}"
        else
            echo -e "${RED}❌ Failed to refresh AWS SSO credentials${NC}"
            echo "Please run 'aws sso login' manually and try again"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ AWS credentials are valid${NC}"
    fi
}

# Function to get AWS account ID
get_aws_account_id() {
    # First refresh credentials if needed
    refresh_aws_credentials
    
    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✅ AWS Account ID: $AWS_ACCOUNT_ID${NC}"
}

# Function to handle Lumigo token
setup_lumigo_token() {
    # Store token in session file for reuse
    TOKEN_FILE=".lumigo_token"
    
    # Check if we have a stored token and no token was provided
    if [ -z "$LUMIGO_TOKEN" ] && [ -f "$TOKEN_FILE" ]; then
        LUMIGO_TOKEN=$(cat "$TOKEN_FILE")
        echo -e "${GREEN}✅ Using stored Lumigo token from previous session${NC}"
    fi
    
    if [ -z "$LUMIGO_TOKEN" ]; then
        echo -e "${YELLOW}⚠️  No Lumigo token provided.${NC}"
        echo "You can:"
        echo "1. Provide it as an argument: ./deploy.sh YOUR_TOKEN"
        echo "2. Set it as environment variable: export LUMIGO_TRACER_TOKEN=YOUR_TOKEN"
        echo "3. Configure it later in the Lambda function"
        echo ""
        read -p "Enter your Lumigo token (or press Enter to skip): " LUMIGO_TOKEN_INPUT
        
        if [ ! -z "$LUMIGO_TOKEN_INPUT" ]; then
            LUMIGO_TOKEN="$LUMIGO_TOKEN_INPUT"
            # Store the token for future sessions
            echo "$LUMIGO_TOKEN" > "$TOKEN_FILE"
            echo -e "${GREEN}✅ Lumigo token set and stored for future sessions${NC}"
        else
            echo -e "${YELLOW}⚠️  No token provided. Function will work but won't send traces to Lumigo.${NC}"
        fi
    else
        echo -e "${GREEN}✅ Lumigo token provided${NC}"
        # Store the token for future sessions if it was provided as argument
        if [ ! -f "$TOKEN_FILE" ]; then
            echo "$LUMIGO_TOKEN" > "$TOKEN_FILE"
            echo -e "${GREEN}✅ Lumigo token stored for future sessions${NC}"
        fi
    fi
}

# Function to setup IAM role
setup_iam_role() {
    echo -e "${BLUE}🔧 Setting up IAM role...${NC}"
    
    ROLE_NAME="lambda-execution-role"
    
    # Create role if it doesn't exist
    if ! aws iam get-role --role-name $ROLE_NAME > /dev/null 2>&1; then
        echo "Creating IAM role: $ROLE_NAME"
        
        # Create trust policy
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
        
        aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document file:///tmp/trust-policy.json \
            --description "Execution role for Lambda function with Lumigo instrumentation"
        
        echo -e "${GREEN}✅ Created IAM role${NC}"
    else
        echo -e "${GREEN}✅ IAM role already exists${NC}"
    fi
    
    # Attach policies
    echo "Attaching policies..."
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
    aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess
    
    echo -e "${GREEN}✅ IAM role configured${NC}"
}

# Function to build and push Docker image
build_and_push() {
    echo -e "${BLUE}📦 Building Docker image...${NC}"
    
    # Create a clean virtual environment for building
    echo -e "${BLUE}🧹 Creating clean build environment...${NC}"
    python3 -m venv .venv-build
    source .venv-build/bin/activate
    
    # Build Docker image
    docker build --platform linux/amd64 -t $ECR_REPOSITORY .
    
    # Deactivate virtual environment
    deactivate
    rm -rf .venv-build
    
    echo -e "${BLUE}🔐 Logging into ECR...${NC}"
    aws_operation_with_retry aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
    
    # Create ECR repository if it doesn't exist
    echo -e "${BLUE}🏗️  Checking ECR repository...${NC}"
    if ! aws_operation_with_retry aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $REGION > /dev/null 2>&1; then
        echo "Creating ECR repository: $ECR_REPOSITORY"
        aws_operation_with_retry aws ecr create-repository --repository-name $ECR_REPOSITORY --region $REGION
        echo -e "${GREEN}✅ ECR repository created${NC}"
    else
        echo -e "${YELLOW}⚠️  ECR repository already exists${NC}"
    fi
    
    echo -e "${BLUE}🏷️  Tagging image...${NC}"
    docker tag $ECR_REPOSITORY:latest $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:latest
    
    echo -e "${BLUE}📤 Pushing to ECR...${NC}"
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:latest
    
    echo -e "${GREEN}✅ Image pushed successfully${NC}"
}

# Function to deploy Lambda function
deploy_lambda() {
    echo -e "${BLUE}🚀 Deploying Lambda function...${NC}"
    
    # Get AWS account ID if not already set
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        get_aws_account_id
    fi
    
    # Build and push the Docker image first
    build_and_push
    
    # Get role ARN dynamically
    ROLE_ARN=$(aws_operation_with_retry aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
    
    IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:latest"
    
    # Check if function exists
    if aws_operation_with_retry aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
        echo -e "${YELLOW}⚠️  Lambda function '$FUNCTION_NAME' already exists.${NC}"
        echo "What would you like to do?"
        echo "1. Update existing function (redeploy)"
        echo "2. Test existing function"
        echo "3. Cancel"
        read -p "Choose an option (1-3): " choice
        
        case $choice in
            1)
                echo -e "${BLUE}Updating existing Lambda function...${NC}"
                aws_operation_with_retry aws lambda update-function-code \
                    --function-name $FUNCTION_NAME \
                    --image-uri $IMAGE_URI \
                    --region $REGION
                
                # Wait for function to be ready after code update
                echo -e "${BLUE}Waiting for Lambda function to be ready after code update...${NC}"
                while true; do
                    STATUS=$(aws_operation_with_retry aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.State' --output text)
                    UPDATE_STATUS=$(aws_operation_with_retry aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.LastUpdateStatus' --output text)
                    
                    if [[ "$STATUS" == "Active" && "$UPDATE_STATUS" == "Successful" ]]; then
                        echo -e "${GREEN}✅ Function is ready after code update${NC}"
                        break
                    elif [[ "$UPDATE_STATUS" == "Failed" ]]; then
                        echo -e "${RED}❌ Function update failed${NC}"
                        return 1
                    else
                        echo "Function state: $STATUS, update status: $UPDATE_STATUS, waiting..."
                        sleep 5
                    fi
                done
                
                echo -e "${BLUE}Updating function configuration...${NC}"
                aws_operation_with_retry aws lambda update-function-configuration \
                    --function-name $FUNCTION_NAME \
                    --timeout 60 \
                    --memory-size 512 \
                    --environment Variables="{
                        OTEL_SERVICE_NAME=lambda-python-lumigo-container,
                        LUMIGO_TRACER_TOKEN=$LUMIGO_TOKEN,
                        LUMIGO_ENABLE_LOGS=true,
                        DYNAMODB_TABLE_NAME=example-table,
                        S3_BUCKET_NAME=example-bucket
                    }" \
                    --region $REGION
                
                # Wait for function to be ready after configuration update
                echo -e "${BLUE}Waiting for Lambda function to be ready after configuration update...${NC}"
                while true; do
                    STATUS=$(aws_operation_with_retry aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.State' --output text)
                    UPDATE_STATUS=$(aws_operation_with_retry aws lambda get-function --function-name $FUNCTION_NAME --region $REGION --query 'Configuration.LastUpdateStatus' --output text)
                    
                    if [[ "$STATUS" == "Active" && "$UPDATE_STATUS" == "Successful" ]]; then
                        echo -e "${GREEN}✅ Function is ready after configuration update${NC}"
                        break
                    elif [[ "$UPDATE_STATUS" == "Failed" ]]; then
                        echo -e "${RED}❌ Function configuration update failed${NC}"
                        return 1
                    else
                        echo "Function state: $STATUS, update status: $UPDATE_STATUS, waiting..."
                        sleep 5
                    fi
                done
                
                echo -e "${GREEN}✅ Lambda function updated successfully${NC}"
                ;;
            2)
                test_function_interactive
                return
                ;;
            3)
                echo -e "${YELLOW}⚠️  Deployment cancelled${NC}"
                return
                ;;
            *)
                echo -e "${RED}❌ Invalid option${NC}"
                return
                ;;
        esac
    else
        echo -e "${BLUE}Creating new Lambda function...${NC}"
        aws_operation_with_retry aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --package-type Image \
            --code ImageUri=$IMAGE_URI \
            --role $ROLE_ARN \
            --timeout 60 \
            --memory-size 512 \
            --environment Variables="{
                OTEL_SERVICE_NAME=lambda-python-lumigo-container,
                LUMIGO_TRACER_TOKEN=$LUMIGO_TOKEN,
                LUMIGO_ENABLE_LOGS=true,
                DYNAMODB_TABLE_NAME=example-table,
                S3_BUCKET_NAME=example-bucket
            }" \
            --region $REGION
        
        echo -e "${GREEN}✅ Lambda function created successfully${NC}"
    fi
    
    echo -e "${BLUE}Waiting for function to be active...${NC}"
    aws_operation_with_retry aws lambda wait function-active --function-name $FUNCTION_NAME --region $REGION
    echo -e "${GREEN}✅ Lambda function deployed successfully${NC}"
}

# Function to test the function
test_function() {
    echo -e "${BLUE}🧪 Testing Lambda function...${NC}"
    
    # Wait for function to be ready
    echo "Waiting for Lambda function to be ready..."
    while true; do
        check_aws_credentials || return 1
        FUNCTION_STATE=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.State' --output text 2>/dev/null || echo "Unknown")
        if [ "$FUNCTION_STATE" = "Active" ]; then
            echo -e "${GREEN}✅ Function is ready${NC}"
            break
        elif [ "$FUNCTION_STATE" = "Failed" ]; then
            echo -e "${RED}❌ Function creation failed${NC}"
            return 1
        else
            echo "Function state: $FUNCTION_STATE, waiting..."
            sleep 5
        fi
    done
    
    test_function_interactive
}

# Function for interactive testing
test_function_interactive() {
    echo -e "${BLUE}🧪 Interactive Lambda Testing${NC}"
    echo "Choose a test event:"
    echo "1. Use default test event (from events/test-event.json) - All operations"
    echo "2. Use RDS-only test event (from events/test-event-rds-only.json) - RDS operations only"
    echo "3. Use simple test event"
    echo "4. Enter custom JSON event"
    echo "5. Skip testing"
    read -p "Choose an option (1-5): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            if [ -f "events/test-event.json" ]; then
                echo "Using events/test-event.json (all operations)..."
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload file://events/test-event.json \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            else
                echo -e "${YELLOW}⚠️  events/test-event.json not found, using simple test event${NC}"
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload '{"data": "hello from default test", "test": true}' \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            fi
            ;;
        2)
            if [ -f "events/test-event-rds-only.json" ]; then
                echo "Using events/test-event-rds-only.json (RDS operations only)..."
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload file://events/test-event-rds-only.json \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            else
                echo -e "${YELLOW}⚠️  events/test-event-rds-only.json not found, using RDS-only payload${NC}"
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload '{"data": "hello from rds test", "test": true, "actions": {"api_operations": false, "s3_operations": false, "database_operations": false, "rds_operations": true}}' \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            fi
            ;;
        3)
            echo "Using simple test event..."
            aws lambda invoke \
                --function-name $FUNCTION_NAME \
                --payload '{"data": "hello from simple test", "test": true, "source": "interactive"}' \
                --cli-binary-format raw-in-base64-out \
                response.json
            ;;
        4)
            echo "Enter your custom JSON event (press Enter when done):"
            echo "Example: {\"data\": \"hello\", \"test\": true, \"actions\": {\"rds_operations\": true}}"
            read -p "JSON event: " CUSTOM_EVENT
            if [ ! -z "$CUSTOM_EVENT" ]; then
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload "$CUSTOM_EVENT" \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            else
                echo -e "${YELLOW}⚠️  No event provided, skipping test${NC}"
                return
            fi
            ;;
        5)
            echo -e "${YELLOW}⚠️  Skipping test${NC}"
            return
            ;;
        *)
            echo -e "${RED}❌ Invalid option${NC}"
            return
            ;;
    esac
    
    echo -e "${GREEN}✅ Function invoked successfully${NC}"
    
    if [ -f "response.json" ]; then
        echo -e "${BLUE}📄 Response:${NC}"
        cat response.json | jq '.' 2>/dev/null || cat response.json
    fi
    
    echo ""
    echo -e "${BLUE}📊 To see the full execution details:${NC}"
    echo "1. Check CloudWatch logs: aws logs describe-log-groups --log-group-name-prefix /aws/lambda/$FUNCTION_NAME"
    echo "2. View recent logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
    if [ ! -z "$LUMIGO_TOKEN" ]; then
        echo "3. Monitor traces in Lumigo dashboard"
    fi
}

# Function to handle AWS operations with automatic credential refresh
aws_operation_with_retry() {
    local max_retries=3
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if "$@"; then
            return 0
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                echo -e "${YELLOW}⚠️  AWS operation failed, attempting to refresh credentials...${NC}"
                if refresh_aws_credentials; then
                    echo -e "${BLUE}🔄 Retrying AWS operation...${NC}"
                    continue
                else
                    echo -e "${RED}❌ Failed to refresh credentials, cannot retry${NC}"
                    return 1
                fi
            else
                echo -e "${RED}❌ AWS operation failed after $max_retries attempts${NC}"
                return 1
            fi
        fi
    done
}

# Function to check AWS SSO configuration
check_aws_sso_config() {
    echo -e "${BLUE}🔍 Checking AWS SSO configuration...${NC}"
    
    # Check if AWS CLI is configured for SSO
    if aws configure list --profile default 2>/dev/null | grep -q "sso"; then
        echo -e "${GREEN}✅ AWS SSO is configured${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  AWS SSO is not configured${NC}"
        echo ""
        echo -e "${BLUE}📋 AWS SSO Setup Instructions:${NC}"
        echo "1. Run: aws configure sso"
        echo "2. Enter your SSO start URL (e.g., https://your-sso-portal.awsapps.com/start)"
        echo "3. Enter your SSO region (e.g., us-east-1)"
        echo "4. Choose your account and role"
        echo "5. Run: aws sso login"
        echo ""
        echo -e "${YELLOW}💡 Or use traditional IAM credentials:${NC}"
        echo "Run: aws configure"
        echo ""
        read -p "Would you like to configure AWS SSO now? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}🔄 Starting AWS SSO configuration...${NC}"
            aws configure sso
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ AWS SSO configured successfully${NC}"
                return 0
            else
                echo -e "${RED}❌ AWS SSO configuration failed${NC}"
                return 1
            fi
        else
            echo -e "${YELLOW}⚠️  Please configure AWS credentials manually and try again${NC}"
            return 1
        fi
    fi
}

# Main menu function
main_menu() {
    echo ""
    echo -e "${BLUE}🔄 Main Menu${NC}"
    echo "=================="
    echo "1. 🧪 Test existing Lambda function"
    echo "2. 🚀 Deploy new Lambda function"
    echo "3. ❌ Exit"
    echo ""
    read -p "Choose an option (1-3): " choice
    
    case $choice in
        1)
            test_function_interactive
            main_menu  # Return to main menu after testing
            ;;
        2)
            deploy_lambda
            main_menu  # Return to main menu after deployment
            ;;
        3)
            echo -e "${GREEN}👋 Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Invalid option. Please try again.${NC}"
            main_menu
            ;;
    esac
}

# Main execution
main() {
    echo -e "${BLUE}🚀 Turnkey Lambda Deployment with Lumigo${NC}"
    echo "=========================================="
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Setup IAM role
    setup_iam_role
    
    # Setup Lumigo token
    setup_lumigo_token
    
    # Check if function exists and show main menu
    if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
        echo -e "${GREEN}✅ Lambda function '$FUNCTION_NAME' exists${NC}"
        main_menu
    else
        echo -e "${YELLOW}⚠️  Lambda function '$FUNCTION_NAME' does not exist${NC}"
        echo "Would you like to deploy it now? (y/n): "
        read -p "" deploy_choice
        if [[ $deploy_choice =~ ^[Yy]$ ]]; then
            deploy_lambda
            main_menu
        else
            echo -e "${GREEN}👋 Goodbye!${NC}"
            exit 0
        fi
    fi
}

# Run main function
main 