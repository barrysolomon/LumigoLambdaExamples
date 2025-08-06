import json
import os
import time
import logging
import boto3
import uuid
from datetime import datetime
from opentelemetry import trace
from boto3 import client
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb_client = boto3.client('dynamodb')

def safe_json_serialize(obj):
    """
    Safely serialize objects that may contain datetime or other non-JSON serializable types.
    """
    def default_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    return json.dumps(obj, default=default_serializer)

class DynamoDBDAL:
    """
    Data Access Layer for DynamoDB operations with built-in Lumigo instrumentation.
    This class encapsulates all DynamoDB operations with proper logging and execution tags.
    """
    
    def __init__(self, table_name=None):
        """
        Initialize the DAL with a specific table name or use round-robin selection.
        """
        self.dynamodb = client('dynamodb')
        self.table_name = table_name or "example-table"
    
    def create_item(self, item):
        """Create an item in DynamoDB table."""
        try:
            response = self.dynamodb.put_item(
                TableName=self.table_name,
                Item=item
            )
            logger.info(f"DynamoDB Create - Item created successfully")
            return response
        except Exception as e:
            logger.error(f"DynamoDB Create - Error: {str(e)}")
            raise
    
    def read_item(self, item_id):
        """Read an item from DynamoDB table."""
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'id': {'S': item_id}}
            )
            logger.info(f"DynamoDB Read - Item retrieved successfully")
            return response
        except Exception as e:
            logger.error(f"DynamoDB Read - Error: {str(e)}")
            raise
    
    def update_item(self, item_id, updates):
        """Update an item in DynamoDB table."""
        try:
            update_expression = "SET "
            expression_values = {}
            
            for key, value in updates.items():
                update_expression += f"#{key} = :{key}, "
                expression_values[f":{key}"] = {'S': str(value)}
                expression_values[f"#{key}"] = key
            
            update_expression = update_expression.rstrip(", ")
            
            response = self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'id': {'S': item_id}},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_values,
                ReturnValues="ALL_NEW"
            )
            logger.info(f"DynamoDB Update - Item updated successfully")
            return response
        except Exception as e:
            logger.error(f"DynamoDB Update - Error: {str(e)}")
            raise
    
    def delete_item(self, item_id):
        """Delete an item from DynamoDB table."""
        try:
            response = self.dynamodb.delete_item(
                TableName=self.table_name,
                Key={'id': {'S': item_id}}
            )
            logger.info(f"DynamoDB Delete - Item deleted successfully")
            return response
        except Exception as e:
            logger.error(f"DynamoDB Delete - Error: {str(e)}")
            raise
    
    def ensure_table_exists(self):
        """Ensure DynamoDB table exists, create if it doesn't."""
        try:
            # Check if table exists
            self.dynamodb.describe_table(TableName=self.table_name)
            logger.info(f"DynamoDB Table - {self.table_name} already exists")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create table
                logger.info(f"DynamoDB Table - Creating {self.table_name}")
                self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {'AttributeName': 'id', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'id', 'AttributeType': 'S'}
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )
                
                # Wait for table to be active
                waiter = self.dynamodb.get_waiter('table_exists')
                waiter.wait(TableName=self.table_name)
                logger.info(f"DynamoDB Table - {self.table_name} created successfully")
                return True
            else:
                logger.error(f"DynamoDB Table - Error: {str(e)}")
                return False
    
    def create_table(self):
        """
        Create a DynamoDB table for demonstration purposes.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Create_Table",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "action": "create_table_start",
                "aws_service": "DynamoDB",
                "table_config": {
                    "key_schema": [{"AttributeName": "id", "KeyType": "HASH"}],
                    "attribute_definitions": [{"AttributeName": "id", "AttributeType": "S"}],
                    "billing_mode": "PAY_PER_REQUEST"
                }
            }
        }))
        
        try:
            response = dynamodb_client.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        'AttributeName': 'id',
                        'KeyType': 'HASH'  # Partition key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'id',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Create_Table_Success",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "action": "create_table_success",
                    "aws_service": "DynamoDB",
                    "response_metadata": {
                        "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
                    }
                }
            }))
            
            # Wait for table to be active
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Wait_For_Table_Active",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "action": "wait_for_table_active",
                    "aws_service": "DynamoDB"
                }
            }))
            
            waiter = dynamodb_client.get_waiter('table_exists')
            waiter.wait(TableName=self.table_name)
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Table_Active",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "action": "table_active",
                    "aws_service": "DynamoDB"
                }
            }))
            
            return True
            
        except Exception as e:
            if 'Table already exists' in str(e):
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Table_Already_Exists",
                    "Data_Artifacts": {
                        "table_name": self.table_name,
                        "action": "table_already_exists",
                        "aws_service": "DynamoDB"
                    }
                }))
                
                return True
            else:
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Create_Table_Error",
                    "Data_Artifacts": {
                        "table_name": self.table_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "action": "create_table_error",
                        "aws_service": "DynamoDB"
                    }
                }))
                
                return False
    
    def delete_table(self):
        """
        Delete the DynamoDB table for cleanup.
        Can be triggered via event instruction.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Delete_Table",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "action": "delete_table_start",
                "aws_service": "DynamoDB"
            }
        }))
        
        try:
            response = dynamodb_client.delete_table(TableName=self.table_name)
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Delete_Table_Success",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "action": "delete_table_success",
                    "aws_service": "DynamoDB",
                    "response_metadata": {
                        "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
                    }
                }
            }))
            
            return {
                'status': 'success',
                'table_name': self.table_name,
                'message': f'Table {self.table_name} deleted successfully'
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Delete_Table_Error",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "delete_table_error",
                    "aws_service": "DynamoDB"
                }
            }))
            
            return {
                'status': 'failed',
                'table_name': self.table_name,
                'error': str(e),
                'error_type': type(e).__name__
            } 