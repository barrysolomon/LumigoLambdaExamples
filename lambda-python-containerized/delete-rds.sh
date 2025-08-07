#!/bin/bash

# RDS PostgreSQL Cleanup Script
echo "🗑️  RDS PostgreSQL Cleanup"
echo "=========================="

# Configuration
DB_INSTANCE_IDENTIFIER="lumigo-test-postgres"
SECURITY_GROUP_NAME="lumigo-rds-sg"
SUBNET_GROUP_NAME="lumigo-rds-subnet-group"
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

# Function to check if resource exists
resource_exists() {
    local resource_type="$1"
    local resource_name="$2"
    
    case $resource_type in
        "db-instance")
            aws rds describe-db-instances --db-instance-identifier "$resource_name" > /dev/null 2>&1
            ;;
        "security-group")
            aws ec2 describe-security-groups --group-names "$resource_name" > /dev/null 2>&1
            ;;
        "subnet-group")
            aws rds describe-db-subnet-groups --db-subnet-group-name "$resource_name" > /dev/null 2>&1
            ;;
    esac
}

# Delete RDS Instance
echo "🗄️  Checking RDS instance status..."
if resource_exists "db-instance" "$DB_INSTANCE_IDENTIFIER"; then
    echo "📊 Getting instance status..."
    INSTANCE_STATUS=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text 2>/dev/null)
    
    echo "📈 Instance status: $INSTANCE_STATUS"
    
    if [ "$INSTANCE_STATUS" = "available" ]; then
        echo "🗑️  Deleting RDS instance..."
        aws rds delete-db-instance \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --skip-final-snapshot \
            --delete-automated-backups
        
        echo "⏳ Waiting for instance deletion to complete..."
        aws rds wait db-instance-deleted --db-instance-identifier "$DB_INSTANCE_IDENTIFIER"
        echo "✅ RDS instance deleted"
    else
        echo "⚠️  Instance is not in 'available' state. Current status: $INSTANCE_STATUS"
        echo "🔄 Attempting to delete anyway..."
        aws rds delete-db-instance \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --skip-final-snapshot \
            --delete-automated-backups
        echo "✅ Deletion initiated"
    fi
else
    echo "ℹ️  RDS instance '$DB_INSTANCE_IDENTIFIER' not found"
fi

# Delete Security Group
echo "🔒 Checking security group..."
if resource_exists "security-group" "$SECURITY_GROUP_NAME"; then
    echo "🗑️  Deleting security group..."
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
        --group-names "$SECURITY_GROUP_NAME" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)
    
    aws ec2 delete-security-group --group-id "$SECURITY_GROUP_ID"
    echo "✅ Security group deleted"
else
    echo "ℹ️  Security group '$SECURITY_GROUP_NAME' not found"
fi

# Delete Subnet Group
echo "🌐 Checking subnet group..."
if resource_exists "subnet-group" "$SUBNET_GROUP_NAME"; then
    echo "🗑️  Deleting subnet group..."
    aws rds delete-db-subnet-group --db-subnet-group-name "$SUBNET_GROUP_NAME"
    echo "✅ Subnet group deleted"
else
    echo "ℹ️  Subnet group '$SUBNET_GROUP_NAME' not found"
fi

echo ""
echo "🎉 RDS cleanup completed!"
echo ""
echo "📋 Summary:"
echo "   • RDS Instance: $DB_INSTANCE_IDENTIFIER"
echo "   • Security Group: $SECURITY_GROUP_NAME"
echo "   • Subnet Group: $SUBNET_GROUP_NAME"
echo ""
echo "💡 Note: If any resources still exist, they may be in use by other services"
echo "   or require manual cleanup through the AWS Console." 