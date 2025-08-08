#!/bin/bash

# =============================================================================
# COMPREHENSIVE CLEANUP SCRIPT
# =============================================================================
# This script removes all AWS resources created by the Lambda project:
# - S3 buckets (with account ID suffix)
# - DynamoDB tables
# - RDS PostgreSQL instances
# - Lambda functions
# - IAM roles and policies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-1"
FUNCTION_NAME_DIRECT="lambda-python-lumigo-direct"
FUNCTION_NAME_CONTAINER="lambda-python-lumigo-container"
ROLE_NAME_DIRECT="lambda-execution-role-direct"
ROLE_NAME_CONTAINER="lambda-execution-role"
DYNAMODB_TABLE="example-table"
RDS_INSTANCE_ID="lumigo-test-postgres"

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

# Function to check AWS credentials
check_aws_credentials() {
    print_status "Checking AWS credentials..."
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_warning "AWS credentials not found or expired. Attempting to refresh SSO credentials..."
        
        if aws sso login &> /dev/null; then
            print_success "SSO login successful"
        else
            print_error "Failed to login with SSO. Please run 'aws sso login' manually."
            exit 1
        fi
        
        if ! aws sts get-caller-identity &> /dev/null; then
            print_error "AWS credentials are still not working after SSO login."
            exit 1
        fi
    fi
    
    print_success "AWS credentials verified"
}

# Function to get AWS account ID
get_aws_account_id() {
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_success "AWS Account ID: $AWS_ACCOUNT_ID"
}

# Function to cleanup S3 buckets
cleanup_s3_buckets() {
    print_status "Cleaning up S3 buckets..."
    
    # List of bucket name patterns to look for
    BUCKET_PATTERNS=(
        "example-bucket"
        "example-bucket-*"
        "lumigo-test-*"
    )
    
    for pattern in "${BUCKET_PATTERNS[@]}"; do
        # Find buckets matching the pattern
        buckets=$(aws s3api list-buckets --query "Buckets[?contains(Name, '$pattern')].Name" --output text 2>/dev/null || echo "")
        
        if [ ! -z "$buckets" ]; then
            for bucket in $buckets; do
                print_status "Found bucket: $bucket"
                
                # Delete all objects in the bucket
                print_status "Deleting all objects in bucket: $bucket"
                aws s3 rm s3://$bucket --recursive --quiet 2>/dev/null || true
                
                # Delete the bucket
                print_status "Deleting bucket: $bucket"
                aws s3api delete-bucket --bucket $bucket --region $REGION 2>/dev/null && \
                    print_success "Deleted bucket: $bucket" || \
                    print_warning "Could not delete bucket: $bucket (may not exist or have objects)"
            done
        fi
    done
    
    print_success "S3 cleanup completed"
}

# Function to cleanup DynamoDB tables
cleanup_dynamodb_tables() {
    print_status "Cleaning up DynamoDB tables..."
    
    # List of table names to delete
    TABLES=(
        "$DYNAMODB_TABLE"
        "example-table-*"
    )
    
    for table in "${TABLES[@]}"; do
        # List tables matching the pattern
        tables=$(aws dynamodb list-tables --query "TableNames[?contains(@, '$table')]" --output text 2>/dev/null || echo "")
        
        if [ ! -z "$tables" ]; then
            for table_name in $tables; do
                print_status "Deleting DynamoDB table: $table_name"
                aws dynamodb delete-table --table-name $table_name --region $REGION 2>/dev/null && \
                    print_success "Deleted table: $table_name" || \
                    print_warning "Could not delete table: $table_name (may not exist)"
            done
        fi
    done
    
    print_success "DynamoDB cleanup completed"
}

# Function to cleanup RDS instances
cleanup_rds_instances() {
    print_status "Cleaning up RDS instances..."
    
    # Check if RDS instance exists
    if aws rds describe-db-instances --db-instance-identifier $RDS_INSTANCE_ID --region $REGION &>/dev/null; then
        print_status "Found RDS instance: $RDS_INSTANCE_ID"
        
        # Disable deletion protection first
        print_status "Disabling deletion protection..."
        aws rds modify-db-instance \
            --db-instance-identifier $RDS_INSTANCE_ID \
            --no-deletion-protection \
            --apply-immediately \
            --region $REGION 2>/dev/null || true
        
        # Wait for modification to complete
        print_status "Waiting for modification to complete..."
        aws rds wait db-instance-available --db-instance-identifier $RDS_INSTANCE_ID --region $REGION 2>/dev/null || true
        
        # Delete the RDS instance
        print_status "Deleting RDS instance: $RDS_INSTANCE_ID"
        aws rds delete-db-instance \
            --db-instance-identifier $RDS_INSTANCE_ID \
            --skip-final-snapshot \
            --region $REGION 2>/dev/null && \
            print_success "Deleted RDS instance: $RDS_INSTANCE_ID" || \
            print_warning "Could not delete RDS instance: $RDS_INSTANCE_ID"
    else
        print_warning "RDS instance $RDS_INSTANCE_ID not found"
    fi
    
    print_success "RDS cleanup completed"
}

# Function to cleanup Lambda functions
cleanup_lambda_functions() {
    print_status "Cleaning up Lambda functions..."
    
    # List of function names to delete
    FUNCTIONS=(
        "$FUNCTION_NAME_DIRECT"
        "$FUNCTION_NAME_CONTAINER"
    )
    
    for function in "${FUNCTIONS[@]}"; do
        if aws lambda get-function --function-name $function --region $REGION &>/dev/null; then
            print_status "Deleting Lambda function: $function"
            aws lambda delete-function --function-name $function --region $REGION 2>/dev/null && \
                print_success "Deleted Lambda function: $function" || \
                print_warning "Could not delete Lambda function: $function"
        else
            print_warning "Lambda function $function not found"
        fi
    done
    
    print_success "Lambda cleanup completed"
}

# Function to cleanup IAM roles
cleanup_iam_roles() {
    print_status "Cleaning up IAM roles..."
    
    # List of role names to delete
    ROLES=(
        "$ROLE_NAME_DIRECT"
        "$ROLE_NAME_CONTAINER"
    )
    
    for role in "${ROLES[@]}"; do
        if aws iam get-role --role-name $role &>/dev/null; then
            print_status "Cleaning up IAM role: $role"
            
            # Detach managed policies
            policies=$(aws iam list-attached-role-policies --role-name $role --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || echo "")
            for policy in $policies; do
                print_status "Detaching policy: $policy from role: $role"
                aws iam detach-role-policy --role-name $role --policy-arn $policy 2>/dev/null || true
            done
            
            # Delete inline policies
            inline_policies=$(aws iam list-role-policies --role-name $role --query 'PolicyNames[]' --output text 2>/dev/null || echo "")
            for policy in $inline_policies; do
                print_status "Deleting inline policy: $policy from role: $role"
                aws iam delete-role-policy --role-name $role --policy-name $policy 2>/dev/null || true
            done
            
            # Delete the role
            print_status "Deleting IAM role: $role"
            aws iam delete-role --role-name $role 2>/dev/null && \
                print_success "Deleted IAM role: $role" || \
                print_warning "Could not delete IAM role: $role"
        else
            print_warning "IAM role $role not found"
        fi
    done
    
    print_success "IAM cleanup completed"
}

# Function to cleanup ECR repositories
cleanup_ecr_repositories() {
    print_status "Cleaning up ECR repositories..."
    
    REPOSITORIES=(
        "lambda-python-lumigo"
    )
    
    for repo in "${REPOSITORIES[@]}"; do
        if aws ecr describe-repositories --repository-names $repo --region $REGION &>/dev/null; then
            print_status "Deleting ECR repository: $repo"
            
            # Delete all images in the repository
            images=$(aws ecr list-images --repository-name $repo --region $REGION --query 'imageIds[]' --output json 2>/dev/null || echo "[]")
            if [ "$images" != "[]" ]; then
                print_status "Deleting all images in repository: $repo"
                aws ecr batch-delete-image --repository-name $repo --image-ids "$images" --region $REGION 2>/dev/null || true
            fi
            
            # Delete the repository
            aws ecr delete-repository --repository-name $repo --region $REGION 2>/dev/null && \
                print_success "Deleted ECR repository: $repo" || \
                print_warning "Could not delete ECR repository: $repo"
        else
            print_warning "ECR repository $repo not found"
        fi
    done
    
    print_success "ECR cleanup completed"
}

# Function to cleanup CloudWatch log groups
cleanup_cloudwatch_logs() {
    print_status "Cleaning up CloudWatch log groups..."
    
    LOG_GROUPS=(
        "/aws/lambda/$FUNCTION_NAME_DIRECT"
        "/aws/lambda/$FUNCTION_NAME_CONTAINER"
    )
    
    for log_group in "${LOG_GROUPS[@]}"; do
        if aws logs describe-log-groups --log-group-name-prefix $log_group --region $REGION --query 'logGroups[].logGroupName' --output text 2>/dev/null | grep -q $log_group; then
            print_status "Deleting CloudWatch log group: $log_group"
            aws logs delete-log-group --log-group-name $log_group --region $REGION 2>/dev/null && \
                print_success "Deleted log group: $log_group" || \
                print_warning "Could not delete log group: $log_group"
        else
            print_warning "CloudWatch log group $log_group not found"
        fi
    done
    
    print_success "CloudWatch cleanup completed"
}

# Function to show cleanup menu
show_cleanup_menu() {
    echo ""
    echo "🧹 AWS Resource Cleanup Menu"
    echo "============================"
    echo ""
    echo "Choose what to clean up:"
    echo ""
    echo "1. 🗑️  Lambda Functions"
    echo "   • lambda-python-lumigo-direct"
    echo "   • lambda-python-lumigo-container"
    echo ""
    echo "2. 📊 CloudWatch Log Groups"
    echo "   • /aws/lambda/lambda-python-lumigo-direct"
    echo "   • /aws/lambda/lambda-python-lumigo-container"
    echo ""
    echo "3. 🪣 S3 Buckets"
    echo "   • example-bucket-*"
    echo "   • lumigo-test-*"
    echo ""
    echo "4. 🗄️  DynamoDB Tables"
    echo "   • example-table*"
    echo ""
    echo "5. 🗃️  RDS PostgreSQL Instance"
    echo "   • lumigo-test-postgres"
    echo ""
    echo "6. 🐳 ECR Repositories"
    echo "   • lambda-python-lumigo"
    echo ""
    echo "7. 🔐 IAM Roles and Policies"
    echo "   • lambda-execution-role-direct"
    echo "   • lambda-execution-role"
    echo ""
    echo "8. 🧹 Clean Everything (All Above)"
    echo ""
    echo "0. ❌ Exit"
    echo ""
}

# Function to get user selection
get_user_selection() {
    local selection
    read -p "Enter your choice (0-8): " selection
    echo $selection
}

# Function to confirm cleanup
confirm_cleanup() {
    local resource_type="$1"
    echo ""
    print_warning "⚠️  You are about to delete: $resource_type"
    read -p "Are you sure? This action cannot be undone! (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Cleanup cancelled by user"
        return 1
    fi
    return 0
}

# Main cleanup function
main() {
    echo "🧹 Interactive AWS Resource Cleanup"
    echo "==================================="
    echo ""
    echo "This script allows you to selectively clean up AWS resources."
    echo "Choose which resources you want to remove."
    echo ""
    
    # Check credentials first
    check_aws_credentials
    get_aws_account_id
    
    while true; do
        show_cleanup_menu
        selection=$(get_user_selection)
        
        case $selection in
            0)
                print_success "👋 Goodbye!"
                exit 0
                ;;
            1)
                if confirm_cleanup "Lambda Functions"; then
                    cleanup_lambda_functions
                fi
                ;;
            2)
                if confirm_cleanup "CloudWatch Log Groups"; then
                    cleanup_cloudwatch_logs
                fi
                ;;
            3)
                if confirm_cleanup "S3 Buckets"; then
                    cleanup_s3_buckets
                fi
                ;;
            4)
                if confirm_cleanup "DynamoDB Tables"; then
                    cleanup_dynamodb_tables
                fi
                ;;
            5)
                if confirm_cleanup "RDS PostgreSQL Instance"; then
                    cleanup_rds_instances
                fi
                ;;
            6)
                if confirm_cleanup "ECR Repositories"; then
                    cleanup_ecr_repositories
                fi
                ;;
            7)
                if confirm_cleanup "IAM Roles and Policies"; then
                    cleanup_iam_roles
                fi
                ;;
            8)
                if confirm_cleanup "ALL resources (Lambda, S3, DynamoDB, RDS, ECR, IAM, CloudWatch)"; then
                    print_status "Starting comprehensive cleanup..."
                    cleanup_lambda_functions
                    cleanup_cloudwatch_logs
                    cleanup_s3_buckets
                    cleanup_dynamodb_tables
                    cleanup_rds_instances
                    cleanup_ecr_repositories
                    cleanup_iam_roles
                    
                    echo ""
                    print_success "🎉 Comprehensive cleanup completed!"
                    echo ""
                    echo "📋 Summary of cleaned resources:"
                    echo "• Lambda functions and their logs"
                    echo "• S3 buckets and all objects"
                    echo "• DynamoDB tables and data"
                    echo "• RDS PostgreSQL instance and database"
                    echo "• IAM roles and policies"
                    echo "• ECR repositories and images"
                    echo ""
                    echo "💡 Note: Some resources may take a few minutes to be fully deleted."
                fi
                ;;
            *)
                print_error "Invalid selection. Please choose 0-8."
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Run main function
main "$@" 