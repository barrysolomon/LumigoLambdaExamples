#!/bin/bash

# =============================================================================
# DIRECT AWS LAMBDA DEPLOYMENT SCRIPT
# =============================================================================
# This script deploys the Lambda function directly to AWS as a ZIP package
# without using containers. Much faster for development and testing.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="lambda-python-lumigo-direct"
REGION="us-east-1"
RUNTIME="python3.12"
HANDLER="lambda_function.lambda_handler"
TIMEOUT=30
MEMORY_SIZE=512
ROLE_NAME="lambda-execution-role-direct"

# Function to print colored output
print_status() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    # Check if venv module is available
    if ! python3 -c "import venv" &> /dev/null; then
        print_error "Python venv module is not available. Please install python3-venv."
        exit 1
    fi
    
    # Check if required files exist
    if [[ ! -f "lambda_function.py" ]]; then
        print_error "lambda_function.py not found in current directory."
        exit 1
    fi
    
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt not found in current directory."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup IAM role
setup_iam_role() {
    print_status "Setting up IAM role..."
    
    # Check if role already exists
    if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
        print_warning "IAM role $ROLE_NAME already exists"
        return
    fi
    
    # Create trust policy
    cat > trust-policy.json << EOF
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
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://trust-policy.json \
        --description "Lambda execution role for direct deployment"
    
    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Attach S3 full access policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    # Attach DynamoDB full access policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
    
    # Attach RDS full access policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonRDSFullAccess
    
    # Wait for role to be available
    print_status "Waiting for IAM role to be available..."
    aws iam wait role-exists --role-name $ROLE_NAME
    
    # Clean up
    rm -f trust-policy.json
    
    print_success "IAM role setup completed"
}

# Function to setup Lumigo token
setup_lumigo_token() {
    print_status "Setting up Lumigo token..."
    
    # Check if token file exists
    if [[ -f ".lumigo_token" ]]; then
        LUMIGO_TOKEN=$(cat .lumigo_token)
        print_warning "Using existing Lumigo token from .lumigo_token"
    else
        # Prompt for Lumigo token
        echo -e "${YELLOW}Please enter your Lumigo token (or press Enter to skip):${NC}"
        read -r LUMIGO_TOKEN
        
        if [[ -n "$LUMIGO_TOKEN" ]]; then
            echo "$LUMIGO_TOKEN" > .lumigo_token
            print_success "Lumigo token saved to .lumigo_token"
        else
            print_warning "No Lumigo token provided, using default"
            LUMIGO_TOKEN="t_f8f7b905da964eef89261"
        fi
    fi
}

# Function to create deployment package
create_deployment_package() {
    print_status "Creating deployment package..."
    
    # Store current directory
    CURRENT_DIR=$(pwd)
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    PACKAGE_DIR="$TEMP_DIR/package"
    mkdir -p "$PACKAGE_DIR"
    
    # Copy Lambda function files
    cp lambda_function.py "$PACKAGE_DIR/"
    cp dynamodb_api.py "$PACKAGE_DIR/"
    cp s3_api.py "$PACKAGE_DIR/"
    cp api_calls.py "$PACKAGE_DIR/"
    cp postgresql_api.py "$PACKAGE_DIR/"
    
    # Create a clean virtual environment for dependencies
    print_status "Creating clean virtual environment for dependencies..."
    python3.12 -m venv "$TEMP_DIR/venv"
    source "$TEMP_DIR/venv/bin/activate"
    
    # Install dependencies in clean environment
    print_status "Installing Python dependencies in clean environment..."
    pip install --quiet --upgrade pip
    
    # Install regular dependencies
    pip install --quiet lumigo_tracer lumigo-opentelemetry requests boto3 -t "$PACKAGE_DIR"
    
    # Install psycopg2-binary for AMD64 platform (Lambda runtime)
    print_status "Installing psycopg2-binary for AMD64 platform..."
    pip install --quiet --platform manylinux2014_x86_64 --only-binary=:all: --target "$PACKAGE_DIR" psycopg2-binary==2.9.9
    
    # Deactivate virtual environment
    deactivate
    
    # Create ZIP file in current directory
    cd "$PACKAGE_DIR"
    zip -r lambda-package.zip . -q
    mv lambda-package.zip "$CURRENT_DIR/"
    cd "$CURRENT_DIR"
    
    # Clean up temporary directory but keep the ZIP file
    rm -rf "$TEMP_DIR"
    
    print_success "Deployment package created: lambda-package.zip"
}

# Function to deploy Lambda function
deploy_lambda() {
    print_status "Deploying Lambda function..."
    
    # Create deployment package first
    create_deployment_package
    
    # Get role ARN
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
    
    # Check if function exists
    if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
        print_warning "Lambda function $FUNCTION_NAME already exists"
        echo "What would you like to do?"
        echo "1. Update existing function"
        echo "2. Delete and recreate function"
        echo "3. Cancel"
        read -p "Choose an option (1-3): " choice
        
        case $choice in
            1)
                print_status "Updating existing function..."
                aws lambda update-function-code \
                    --function-name $FUNCTION_NAME \
                    --zip-file fileb://lambda-package.zip \
                    --region $REGION
                
                # Wait for code update to complete
                print_status "Waiting for code update to complete..."
                aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION
                
                aws lambda update-function-configuration \
                    --function-name $FUNCTION_NAME \
                    --runtime $RUNTIME \
                    --handler $HANDLER \
                    --timeout $TIMEOUT \
                    --memory-size $MEMORY_SIZE \
                    --layers arn:aws:lambda:$REGION:114300393969:layer:lumigo-log-collector-amd64:27 \
                    --environment Variables="{
                        OTEL_SERVICE_NAME=$FUNCTION_NAME,
                        LUMIGO_TRACER_TOKEN=$LUMIGO_TOKEN,
                        LUMIGO_ENABLE_LOGS=true,
                        DYNAMODB_TABLE_NAME=example-table,
                        S3_BUCKET_NAME=example-bucket,
                        LUMIGO_LOG_ENDPOINT=https://logs-ga.lumigo-tracer-edge.golumigo.com/api/logs?token=$LUMIGO_TOKEN
                    }" \
                    --region $REGION
                
                # Wait for configuration update to complete
                print_status "Waiting for configuration update to complete..."
                aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION
                ;;
            2)
                print_status "Deleting existing function..."
                aws lambda delete-function --function-name $FUNCTION_NAME --region $REGION
                ;;
            3)
                print_warning "Deployment cancelled"
                return
                ;;
            *)
                print_error "Invalid option"
                return
                ;;
        esac
    fi
    
    # Create new function if it doesn't exist
    if ! aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
        print_status "Creating new Lambda function..."
        aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --runtime $RUNTIME \
            --role $ROLE_ARN \
            --handler $HANDLER \
            --zip-file fileb://lambda-package.zip \
            --timeout $TIMEOUT \
            --memory-size $MEMORY_SIZE \
            --layers arn:aws:lambda:$REGION:114300393969:layer:lumigo-log-collector-amd64:27 \
            --environment Variables="{
                OTEL_SERVICE_NAME=$FUNCTION_NAME,
                LUMIGO_TRACER_TOKEN=$LUMIGO_TOKEN,
                LUMIGO_ENABLE_LOGS=true,
                DYNAMODB_TABLE_NAME=example-table,
                S3_BUCKET_NAME=example-bucket,
                LUMIGO_LOG_ENDPOINT=https://logs-ga.lumigo-tracer-edge.golumigo.com/api/logs?token=$LUMIGO_TOKEN
            }" \
            --region $REGION
    fi
    
    # Wait for function to be active
    print_status "Waiting for function to be active..."
    aws lambda wait function-active --function-name $FUNCTION_NAME --region $REGION
    
    print_success "Lambda function deployed successfully"
    
    # Ask if user wants to test
    read -p "Would you like to test the function? (y/n): " test_choice
    if [[ $test_choice =~ ^[Yy]$ ]]; then
        test_lambda
    fi
    
    echo ""
    show_function_info
}

# Function to test Lambda function
test_lambda() {
    print_status "Testing Lambda function..."
    
    echo "Choose a test event:"
    echo "1. Use default test event (all operations)"
    echo "2. Use RDS-only test event (RDS operations only)"
    echo "3. Use simple test event"
    echo "4. Enter custom JSON event"
    echo "5. Skip testing"
    read -p "Choose an option (1-5): " test_choice
    
    case $test_choice in
        1)
            # Create default test event
            cat > events/test-event.json << EOF
{
  "data": "hello world from lumigo",
  "test": true,
  "timestamp": "2024-01-01T00:00:00Z",
  "user_id": "user123",
  "request_type": "api_call",
  "source": "direct-deploy-script",
  "actions": {
    "api_operations": true,
    "s3_operations": true,
    "database_operations": true,
    "rds_operations": true
  }
}
EOF
            print_status "Using default test event (all operations)..."
            ;;
        2)
            # Create RDS-only test event
            cat > events/test-event-rds-only.json << EOF
{
  "data": "hello world from lumigo",
  "test": true,
  "timestamp": "2024-01-01T00:00:00Z",
  "user_id": "user123",
  "request_type": "rds_test",
  "source": "direct-deploy-script",
  "actions": {
    "api_operations": false,
    "s3_operations": false,
    "database_operations": false,
    "rds_operations": true
  }
}
EOF
            print_status "Using RDS-only test event..."
            ;;
        3)
            # Create simple test event
            cat > events/test-event-simple.json << EOF
{
  "data": "hello from simple test",
  "test": true,
  "source": "direct-deploy-script"
}
EOF
            print_status "Using simple test event..."
            ;;
        4)
            echo "Enter your custom JSON event (press Enter when done):"
            echo "Example: {\"data\": \"hello\", \"test\": true, \"actions\": {\"rds_operations\": true}}"
            read -p "JSON event: " CUSTOM_EVENT
            if [ ! -z "$CUSTOM_EVENT" ]; then
                echo "$CUSTOM_EVENT" > events/test-event-custom.json
                print_status "Using custom test event..."
            else
                print_warning "No event provided, skipping test"
                return
            fi
            ;;
        5)
            print_warning "Skipping test"
            return
            ;;
        *)
            print_error "Invalid option"
            return
            ;;
    esac
    
    # Invoke function
    print_status "Invoking Lambda function..."
    
    # Determine which test event to use based on the choice
    case $test_choice in
        1)
            TEST_EVENT_FILE="events/test-event.json"
            ;;
        2)
            TEST_EVENT_FILE="events/test-event-rds-only.json"
            ;;
        3)
            TEST_EVENT_FILE="events/test-event-simple.json"
            ;;
        4)
            TEST_EVENT_FILE="events/test-event-custom.json"
            ;;
    esac
    
    aws lambda invoke \
        --function-name $FUNCTION_NAME \
        --cli-binary-format raw-in-base64-out \
        --payload file://$TEST_EVENT_FILE \
        --region $REGION \
        response.json
    
    # Display response
    print_success "Function invoked successfully"
    echo "Response:"
    cat response.json | jq '.' 2>/dev/null || cat response.json
    
    # Clean up
    #rm -f test-event.json response.json
    
    print_success "Testing completed"
}

# Function to show function info
show_function_info() {
    print_status "Function Information:"
    echo "Function Name: $FUNCTION_NAME"
    echo "Region: $REGION"
    echo "Runtime: $RUNTIME"
    echo "Handler: $HANDLER"
    echo "Timeout: $TIMEOUT seconds"
    echo "Memory: $MEMORY_SIZE MB"
    echo ""
    echo "To view logs:"
    echo "aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
    echo ""
    echo "To invoke manually:"
    echo "aws lambda invoke --function-name $FUNCTION_NAME --cli-binary-format raw-in-base64-out --payload '{\"data\":\"test\"}' response.json"
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
            test_lambda
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
    echo -e "${BLUE}🚀 Direct AWS Lambda Deployment Script${NC}"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    setup_iam_role
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
main "$@" 