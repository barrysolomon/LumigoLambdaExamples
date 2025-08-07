#!/bin/bash

# RDS PostgreSQL Database Creation Script
# This script creates a small RDS PostgreSQL instance for testing

set -e

# Configuration
DB_INSTANCE_IDENTIFIER="lumigo-test-postgres"
DB_NAME="lumigo_test"
DB_USERNAME="lumigo_admin"
DB_PASSWORD="LumigoTest123!"
DB_INSTANCE_CLASS="db.t3.micro"
DB_ENGINE="postgres"
DB_ENGINE_VERSION="14.18"
ALLOCATED_STORAGE=20
VPC_SECURITY_GROUP_ID=""
SUBNET_GROUP_NAME=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 RDS PostgreSQL Database Creation"
echo "=================================="

# Check AWS credentials
echo "🔍 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured. Please run 'aws configure' or 'aws sso login'${NC}"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
echo -e "${GREEN}✅ AWS credentials valid - Account: $AWS_ACCOUNT_ID, Region: $AWS_REGION${NC}"

# Check if RDS instance already exists
echo "🔍 Checking if RDS instance already exists..."
if aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" --region "$AWS_REGION" &> /dev/null; then
    echo -e "${YELLOW}⚠️  RDS instance '$DB_INSTANCE_IDENTIFIER' already exists${NC}"
    
    # Get instance status
    INSTANCE_STATUS=$(aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" --query 'DBInstances[0].DBInstanceStatus' --output text --region "$AWS_REGION")
    echo "📊 Instance status: $INSTANCE_STATUS"
    
    if [ "$INSTANCE_STATUS" = "available" ]; then
        echo -e "${GREEN}✅ RDS instance is available${NC}"
        
        # Get endpoint
        DB_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" --query 'DBInstances[0].Endpoint.Address' --output text --region "$AWS_REGION")
        echo "🔗 Database endpoint: $DB_ENDPOINT"
        
        echo ""
        echo "📋 Database Connection Details:"
        echo "================================"
        echo "Host: $DB_ENDPOINT"
        echo "Port: 5432"
        echo "Database: $DB_NAME"
        echo "Username: $DB_USERNAME"
        echo "Password: $DB_PASSWORD"
        echo ""
        echo "🔧 To connect using psql:"
        echo "psql -h $DB_ENDPOINT -U $DB_USERNAME -d $DB_NAME"
        echo ""
        echo "🔧 To connect using AWS CLI:"
        echo "aws rds-data execute-statement --resource-arn arn:aws:rds:$AWS_REGION:$AWS_ACCOUNT_ID:cluster:$DB_INSTANCE_IDENTIFIER --sql 'SELECT version();'"
        
        exit 0
    else
        echo -e "${YELLOW}⏳ RDS instance is in status: $INSTANCE_STATUS${NC}"
        echo "Please wait for the instance to become available..."
        exit 0
    fi
fi

# Create security group for RDS
echo "🔒 Creating security group for RDS..."
SECURITY_GROUP_NAME="lumigo-rds-sg"
SECURITY_GROUP_DESC="Security group for Lumigo RDS PostgreSQL instance"

# Check if security group exists
EXISTING_SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")

if [ "$EXISTING_SG" = "None" ] || [ -z "$EXISTING_SG" ]; then
    echo "Creating new security group..."
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name "$SECURITY_GROUP_NAME" \
        --description "$SECURITY_GROUP_DESC" \
        --region "$AWS_REGION" \
        --query 'GroupId' --output text)
    
    # Add inbound rule for PostgreSQL
    aws ec2 authorize-security-group-ingress \
        --group-id "$SECURITY_GROUP_ID" \
        --protocol tcp \
        --port 5432 \
        --cidr 0.0.0.0/0 \
        --region "$AWS_REGION"
    
    echo -e "${GREEN}✅ Security group created: $SECURITY_GROUP_ID${NC}"
else
    SECURITY_GROUP_ID="$EXISTING_SG"
    echo -e "${GREEN}✅ Using existing security group: $SECURITY_GROUP_ID${NC}"
fi

# Create DB subnet group
echo "🌐 Creating DB subnet group..."
SUBNET_GROUP_NAME="lumigo-db-subnet-group"
SUBNET_GROUP_DESC="Subnet group for Lumigo RDS instance"

# Check if subnet group exists
if ! aws rds describe-db-subnet-groups --db-subnet-group-name "$SUBNET_GROUP_NAME" --region "$AWS_REGION" &> /dev/null; then
    echo "Creating new subnet group..."
    
    # Get default VPC
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
    
    # Get public subnets in the VPC
    SUBNET_IDS=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
        --query 'Subnets[0:2].SubnetId' \
        --output text \
        --region "$AWS_REGION")
    
    # If no public subnets found, use the first 2 subnets but warn
    if [ "$SUBNET_IDS" = "None" ] || [ -z "$SUBNET_IDS" ]; then
        echo "⚠️  No public subnets found, using first 2 subnets (may be private)"
        SUBNET_IDS=$(aws ec2 describe-subnets \
            --filters "Name=vpc-id,Values=$VPC_ID" \
            --query 'Subnets[0:2].SubnetId' \
            --output text \
            --region "$AWS_REGION")
    else
        echo "✅ Found public subnets for RDS"
    fi
    
    aws rds create-db-subnet-group \
        --db-subnet-group-name "$SUBNET_GROUP_NAME" \
        --db-subnet-group-description "$SUBNET_GROUP_DESC" \
        --subnet-ids $SUBNET_IDS \
        --region "$AWS_REGION"
    
    echo -e "${GREEN}✅ DB subnet group created${NC}"
else
    echo -e "${GREEN}✅ Using existing subnet group${NC}"
fi

# Create RDS instance
echo "🗄️  Creating RDS PostgreSQL instance..."
echo "This may take 5-10 minutes..."

aws rds create-db-instance \
    --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
    --db-instance-class "$DB_INSTANCE_CLASS" \
    --engine "$DB_ENGINE" \
    --engine-version "$DB_ENGINE_VERSION" \
    --allocated-storage "$ALLOCATED_STORAGE" \
    --storage-type gp2 \
    --db-name "$DB_NAME" \
    --master-username "$DB_USERNAME" \
    --master-user-password "$DB_PASSWORD" \
    --vpc-security-group-ids "$SECURITY_GROUP_ID" \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" \
    --backup-retention-period 7 \
    --preferred-backup-window "03:00-04:00" \
    --preferred-maintenance-window "sun:04:00-sun:05:00" \
    --storage-encrypted \
    --no-deletion-protection \
    --publicly-accessible \
    --region "$AWS_REGION"

echo -e "${GREEN}✅ RDS instance creation initiated${NC}"
echo ""
echo "⏳ Please wait 5-10 minutes for the instance to become available..."
echo "You can check the status with:"
echo "aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_IDENTIFIER --query 'DBInstances[0].DBInstanceStatus' --output text"
echo ""
echo "🔗 Once available, the endpoint will be:"
echo "aws rds describe-db-instances --db-instance-identifier $DB_INSTANCE_IDENTIFIER --query 'DBInstances[0].Endpoint.Address' --output text"
echo ""
echo "📋 Database Connection Details:"
echo "================================"
echo "Host: [Will be available once instance is ready]"
echo "Port: 5432"
echo "Database: $DB_NAME"
echo "Username: $DB_USERNAME"
echo "Password: $DB_PASSWORD" 