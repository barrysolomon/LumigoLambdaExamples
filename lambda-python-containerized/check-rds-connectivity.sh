#!/bin/bash

# RDS Connectivity Check Script
echo "🔍 RDS PostgreSQL Connectivity Check"
echo "===================================="

# Configuration
DB_INSTANCE_IDENTIFIER="lumigo-test-postgres"
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo "📍 AWS Region: $AWS_REGION"
echo "🗄️  DB Instance: $DB_INSTANCE_IDENTIFIER"

# Check AWS credentials
echo "🔐 Checking AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' or 'aws sso login'"
    exit 1
fi

echo "✅ AWS credentials verified"

# Check if RDS instance exists
echo "🗄️  Checking RDS instance status..."
if aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" > /dev/null 2>&1; then
    INSTANCE_STATUS=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text 2>/dev/null)
    
    echo "📈 Instance status: $INSTANCE_STATUS"
    
    if [ "$INSTANCE_STATUS" = "available" ]; then
        echo "✅ RDS instance is available"
        
        # Get endpoint
        ENDPOINT=$(aws rds describe-db-instances \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --query 'DBInstances[0].Endpoint.Address' \
            --output text 2>/dev/null)
        
        echo "🌐 Endpoint: $ENDPOINT"
        
        # Check if we can reach the endpoint
        echo "🔍 Testing connectivity to RDS endpoint..."
        if nc -z "$ENDPOINT" 5432 2>/dev/null; then
            echo "✅ Port 5432 is reachable"
        else
            echo "❌ Port 5432 is not reachable"
            echo ""
            echo "🔧 Troubleshooting Steps:"
            echo "1. Check if RDS is in a private subnet"
            echo "2. Verify Lambda VPC configuration"
            echo "3. Check security group rules"
            echo "4. Ensure Lambda has proper IAM permissions"
        fi
        
    else
        echo "⚠️  RDS instance is not available (status: $INSTANCE_STATUS)"
        echo "   Wait for the instance to become available before testing"
    fi
    
else
    echo "❌ RDS instance '$DB_INSTANCE_IDENTIFIER' not found"
    echo "   Run './create-rds.sh' to create the instance"
fi

echo ""
echo "📋 Lambda VPC Configuration Check:"
echo "=================================="

# Check if Lambda is configured with VPC
LAMBDA_FUNCTION_NAME="lambda-python-lumigo-container"
if aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" > /dev/null 2>&1; then
    VPC_CONFIG=$(aws lambda get-function \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --query 'Configuration.VpcConfig' \
        --output json 2>/dev/null)
    
    if [ "$VPC_CONFIG" = "null" ] || [ "$VPC_CONFIG" = "{}" ]; then
        echo "⚠️  Lambda function is NOT configured with VPC"
        echo "   This may cause connectivity issues with RDS in private subnets"
        echo ""
        echo "💡 Solutions:"
        echo "1. Configure Lambda with VPC settings"
        echo "2. Move RDS to public subnet (not recommended for production)"
        echo "3. Use RDS Proxy for better connectivity"
    else
        echo "✅ Lambda function is configured with VPC"
        echo "   VPC Config: $VPC_CONFIG"
    fi
else
    echo "⚠️  Lambda function '$LAMBDA_FUNCTION_NAME' not found"
    echo "   Deploy the function first using './deploy-containerized.sh'"
fi

echo ""
echo "🔧 Quick Fixes:"
echo "==============="
echo "1. For testing: Move RDS to public subnet temporarily"
echo "2. For production: Configure Lambda with proper VPC settings"
echo "3. Alternative: Use RDS Proxy for better connectivity"
echo ""
echo "📚 Documentation:"
echo "================="
echo "- AWS Lambda VPC Configuration: https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html"
echo "- RDS Connectivity: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.Scenarios.html" 