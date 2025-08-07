#!/bin/bash

# Recreate RDS PostgreSQL with Public Access
echo "🔄 Recreating RDS PostgreSQL with Public Access"
echo "================================================"

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
        echo "🔓 Disabling deletion protection..."
        aws rds modify-db-instance \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --no-deletion-protection
        
        echo "⏳ Waiting for modification to complete..."
        aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_IDENTIFIER"
        
        echo "🗑️  Deleting existing RDS instance..."
        aws rds delete-db-instance \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --skip-final-snapshot \
            --delete-automated-backups
        
        echo "⏳ Waiting for instance deletion to complete..."
        aws rds wait db-instance-deleted --db-instance-identifier "$DB_INSTANCE_IDENTIFIER"
        echo "✅ RDS instance deleted"
    else
        echo "⚠️  Instance is not in 'available' state. Current status: $INSTANCE_STATUS"
        echo "🔄 Attempting to disable deletion protection and delete anyway..."
        aws rds modify-db-instance \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --no-deletion-protection
        
        aws rds delete-db-instance \
            --db-instance-identifier "$DB_INSTANCE_IDENTIFIER" \
            --skip-final-snapshot \
            --delete-automated-backups
        echo "✅ Deletion initiated"
    fi
else
    echo "ℹ️  RDS instance '$DB_INSTANCE_IDENTIFIER' not found"
fi

echo ""
echo "🔄 Recreating RDS instance with public access..."
echo "This will take 5-10 minutes..."

# Run the create-rds.sh script
./create-rds.sh

echo ""
echo "✅ RDS recreation completed!"
echo ""
echo "📋 Next Steps:"
echo "1. Wait 5-10 minutes for the instance to become available"
echo "2. Test connectivity: ./check-rds-connectivity.sh"
echo "3. Deploy Lambda: ./deploy-containerized.sh"
echo "4. Test with RDS only: Update test-event.json to enable only rds_operations" 