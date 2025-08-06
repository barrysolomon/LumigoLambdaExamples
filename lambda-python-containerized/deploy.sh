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

# Default values
LUMIGO_TOKEN=${1:-""}
AWS_REGION=${AWS_DEFAULT_REGION:-"us-east-1"}
FUNCTION_NAME="lambda-python-lumigo-example"
ECR_REPO_NAME="lambda-python-lumigo"

echo -e "${BLUE}🚀 Turnkey Lambda Deployment with Lumigo${NC}"
echo "================================================"

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
    
    # Check AWS credentials and refresh if needed
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  AWS credentials not available or expired.${NC}"
        echo "Attempting to refresh AWS SSO credentials..."
        
        if aws sso login > /dev/null 2>&1; then
            echo -e "${GREEN}✅ AWS SSO credentials refreshed successfully${NC}"
        else
            echo -e "${RED}❌ Failed to refresh AWS credentials.${NC}"
            echo "Please run 'aws sso login' manually or configure AWS credentials."
            exit 1
        fi
    fi
    
    # Additional check for SSO token expiration during operations
    check_aws_credentials() {
        if ! aws sts get-caller-identity > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  AWS SSO token expired during operation.${NC}"
            read -p "Would you like to refresh AWS credentials now? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                if aws sso login > /dev/null 2>&1; then
                    echo -e "${GREEN}✅ AWS SSO credentials refreshed successfully${NC}"
                    return 0
                else
                    echo -e "${RED}❌ Failed to refresh AWS credentials.${NC}"
                    return 1
                fi
            else
                echo -e "${RED}❌ Cannot continue without valid AWS credentials.${NC}"
                return 1
            fi
        fi
        return 0
    }
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to get AWS account ID
get_aws_account_id() {
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
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
    
    echo -e "${GREEN}✅ IAM role configured${NC}"
}

# Function to build and push Docker image
build_and_push() {
    echo -e "${BLUE}📦 Building Docker image...${NC}"
    docker build --platform linux/amd64 -t $ECR_REPO_NAME .
    
    echo -e "${BLUE}🔐 Logging into ECR...${NC}"
    check_aws_credentials || return 1
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Create ECR repository if it doesn't exist
    echo -e "${BLUE}🏗️  Checking ECR repository...${NC}"
    if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION > /dev/null 2>&1; then
        echo "Creating ECR repository: $ECR_REPO_NAME"
        aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
        echo -e "${GREEN}✅ ECR repository created${NC}"
    else
        echo -e "${GREEN}✅ ECR repository already exists${NC}"
    fi
    
    echo -e "${BLUE}🏷️  Tagging image...${NC}"
    docker tag $ECR_REPO_NAME:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
    
    echo -e "${BLUE}📤 Pushing to ECR...${NC}"
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest
    
    echo -e "${GREEN}✅ Image pushed successfully${NC}"
}

# Function to deploy Lambda function
deploy_lambda() {
    echo -e "${BLUE}🚀 Deploying Lambda function...${NC}"
    
    IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest"
    ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/lambda-execution-role"
    
    # Check if function exists
    check_aws_credentials || return 1
    if aws lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Lambda function '$FUNCTION_NAME' already exists.${NC}"
        echo "What would you like to do?"
        echo "1. Update existing function (redeploy)"
        echo "2. Test existing function"
        echo "3. Cancel"
        read -p "Choose an option (1-3): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[1]$ ]]; then
            echo "Updating existing Lambda function..."
            check_aws_credentials || return 1
            aws lambda update-function-code --function-name $FUNCTION_NAME --image-uri $IMAGE_URI
            
            # Wait for function to be ready after code update
            echo "Waiting for Lambda function to be ready after code update..."
            while true; do
                FUNCTION_STATE=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.State' --output text 2>/dev/null || echo "Unknown")
                UPDATE_STATUS=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.LastUpdateStatus' --output text 2>/dev/null || echo "Unknown")
                if [ "$FUNCTION_STATE" = "Active" ] && [ "$UPDATE_STATUS" = "Successful" ]; then
                    echo -e "${GREEN}✅ Function is ready after code update${NC}"
                    break
                elif [ "$FUNCTION_STATE" = "Failed" ] || [ "$UPDATE_STATUS" = "Failed" ]; then
                    echo -e "${RED}❌ Function code update failed${NC}"
                    return 1
                else
                    echo "Function state: $FUNCTION_STATE, update status: $UPDATE_STATUS, waiting..."
                    sleep 5
                fi
            done
            
            # Update environment variables if token is provided
            if [ ! -z "$LUMIGO_TOKEN" ]; then
                echo "Updating function configuration..."
                check_aws_credentials || return 1
                aws lambda update-function-configuration \
                    --function-name $FUNCTION_NAME \
                    --environment Variables="{
                        LUMIGO_TRACER_TOKEN=$LUMIGO_TOKEN,
                        OTEL_SERVICE_NAME=lambda-python-lumigo-example,
                        LUMIGO_ENABLE_LOGS=true,
                        DYNAMODB_TABLE_NAME=example-table,
                        S3_BUCKET_NAME=example-bucket
                    }" \
                    --timeout 30 \
                    --memory-size 512
                
                # Wait for function to be ready after configuration update
                echo "Waiting for Lambda function to be ready after configuration update..."
                while true; do
                    FUNCTION_STATE=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.State' --output text 2>/dev/null || echo "Unknown")
                    UPDATE_STATUS=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.LastUpdateStatus' --output text 2>/dev/null || echo "Unknown")
                    if [ "$FUNCTION_STATE" = "Active" ] && [ "$UPDATE_STATUS" = "Successful" ]; then
                        echo -e "${GREEN}✅ Function is ready after configuration update${NC}"
                        break
                    elif [ "$FUNCTION_STATE" = "Failed" ] || [ "$UPDATE_STATUS" = "Failed" ]; then
                        echo -e "${RED}❌ Function configuration update failed${NC}"
                        return 1
                    else
                        echo "Function state: $FUNCTION_STATE, update status: $UPDATE_STATUS, waiting..."
                        sleep 5
                    fi
                done
            fi
            
            echo -e "${GREEN}✅ Lambda function updated successfully${NC}"
        elif [[ $REPLY =~ ^[2]$ ]]; then
            echo -e "${BLUE}🧪 Testing existing function...${NC}"
            test_function_interactive
            return
        else
            echo "Deployment cancelled."
            exit 0
        fi
    else
        echo "Creating new Lambda function..."
        
        # Create function with environment variables if token is provided
        check_aws_credentials || return 1
        if [ ! -z "$LUMIGO_TOKEN" ]; then
            aws lambda create-function \
                --function-name $FUNCTION_NAME \
                --package-type Image \
                --code ImageUri=$IMAGE_URI \
                --role $ROLE_ARN \
                --environment Variables="{
                    LUMIGO_TRACER_TOKEN=$LUMIGO_TOKEN,
                    OTEL_SERVICE_NAME=lambda-python-lumigo-example,
                    LUMIGO_ENABLE_LOGS=true,
                    DYNAMODB_TABLE_NAME=example-table,
                    S3_BUCKET_NAME=example-bucket
                }" \
                --timeout 30 \
                --memory-size 512
        else
            check_aws_credentials || return 1
            aws lambda create-function \
                --function-name $FUNCTION_NAME \
                --package-type Image \
                --code ImageUri=$IMAGE_URI \
                --role $ROLE_ARN \
                --timeout 30 \
                --memory-size 512
        fi
        
        echo -e "${GREEN}✅ Lambda function created${NC}"
        
        # Wait for function to be ready
        echo "Waiting for Lambda function to be ready..."
        while true; do
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
    fi
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
    echo "1. Use default test event (from test-event.json)"
    echo "2. Use simple test event"
    echo "3. Enter custom JSON event"
    echo "4. Skip testing"
    read -p "Choose an option (1-4): " -n 1 -r
    echo
    
    case $REPLY in
        1)
            if [ -f "test-event.json" ]; then
                echo "Using test-event.json..."
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload file://test-event.json \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            else
                echo -e "${YELLOW}⚠️  test-event.json not found, using simple test event${NC}"
                aws lambda invoke \
                    --function-name $FUNCTION_NAME \
                    --payload '{"data": "hello from default test", "test": true}' \
                    --cli-binary-format raw-in-base64-out \
                    response.json
            fi
            ;;
        2)
            echo "Using simple test event..."
            aws lambda invoke \
                --function-name $FUNCTION_NAME \
                --payload '{"data": "hello from simple test", "test": true, "source": "interactive"}' \
                --cli-binary-format raw-in-base64-out \
                response.json
            ;;
        3)
            echo "Enter your custom JSON event (press Enter when done):"
            echo "Example: {\"data\": \"hello\", \"test\": true}"
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
        4)
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

# Main execution
main() {
    check_prerequisites
    get_aws_account_id
    setup_lumigo_token
    setup_iam_role
    build_and_push
    deploy_lambda
    test_function
    
    echo ""
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📋 Summary:${NC}"
    echo "Function Name: $FUNCTION_NAME"
    echo "Region: $AWS_REGION"
    echo "Image: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest"
    echo ""
    echo -e "${BLUE}🔗 Next steps:${NC}"
    echo "1. View function in AWS Lambda console"
    if [ ! -z "$LUMIGO_TOKEN" ]; then
        echo "2. Monitor traces in Lumigo dashboard"
    else
        echo "2. Set LUMIGO_TRACER_TOKEN in Lambda environment variables to enable tracing"
    fi
    echo "3. Check CloudWatch logs for execution details"
    echo ""
    
    # Prompt to call the function
    echo -e "${YELLOW}🧪 Would you like to test the Lambda function now?${NC}"
    read -p "Call the Lambda function? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}🚀 Invoking Lambda function...${NC}"
        aws lambda invoke \
            --function-name $FUNCTION_NAME \
            --payload '{"data": "hello from turnkey deployment", "test": true, "source": "deploy-script"}' \
            --cli-binary-format raw-in-base64-out \
            response.json
        
        echo -e "${GREEN}✅ Function invoked successfully!${NC}"
        
        if [ -f "response.json" ]; then
            echo -e "${BLUE}📄 Function response:${NC}"
            cat response.json | jq '.' 2>/dev/null || cat response.json
        fi
        
        echo ""
        echo -e "${BLUE}📊 To see the full execution details:${NC}"
        echo "1. Check CloudWatch logs: aws logs describe-log-groups --log-group-name-prefix /aws/lambda/$FUNCTION_NAME"
        echo "2. View recent logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
        if [ ! -z "$LUMIGO_TOKEN" ]; then
            echo "3. Monitor traces in Lumigo dashboard"
        fi
    else
        echo -e "${BLUE}ℹ️  You can test the function later with:${NC}"
        echo "aws lambda invoke --function-name $FUNCTION_NAME --payload '{\"test\": true}' response.json"
    fi
}

# Run main function
main 