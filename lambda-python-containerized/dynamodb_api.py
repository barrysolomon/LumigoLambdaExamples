import json
import os
import time
import logging
import boto3
import uuid
from datetime import datetime
from opentelemetry import trace

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
        if table_name:
            self.table_name = table_name
            self.round_robin_index = None
        else:
            # Round-robin through DynamoDB tables
            dynamodb_tables = [
                os.environ.get('DYNAMODB_TABLE_NAME', 'example-table'),
                os.environ.get('DYNAMODB_TABLE_NAME', 'example-table') + '-2',
                os.environ.get('DYNAMODB_TABLE_NAME', 'example-table') + '-3'
            ]
            self.round_robin_index = (int(time.time()) % len(dynamodb_tables))
            self.table_name = dynamodb_tables[self.round_robin_index]
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "Database_Operations",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "aws_service": "DynamoDB",
                "round_robin_index": self.round_robin_index
            }
        }))
    
    def ensure_table_exists(self):
        """
        Check if DynamoDB table exists and create it if needed.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Check_Table_Exists",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "action": "check_table_exists",
                "aws_service": "DynamoDB"
            }
        }))
        
        try:
            try:
                response = dynamodb_client.describe_table(TableName=self.table_name)
                table_status = response['Table']['TableStatus']
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Table_Exists",
                    "Data_Artifacts": {
                        "table_name": self.table_name,
                        "table_status": table_status,
                        "action": "table_exists",
                        "aws_service": "DynamoDB",
                        "table_info": {
                            "creation_date": response['Table'].get('CreationDateTime'),
                            "item_count": response['Table'].get('ItemCount', 0),
                            "table_size_bytes": response['Table'].get('TableSizeBytes', 0)
                        }
                    }
                }))
                
                if table_status == 'ACTIVE':
                    return True
                elif table_status in ['CREATING', 'UPDATING']:
                    logger.info(safe_json_serialize({
                        "Data_Source": "Database_Operations",
                        "Data_Target": "Table_Creating_Updating",
                        "Data_Artifacts": {
                            "table_name": self.table_name,
                            "table_status": table_status,
                            "action": "wait_for_table_active",
                            "aws_service": "DynamoDB"
                        }
                    }))
                    
                    # Wait for table to become active
                    waiter = dynamodb_client.get_waiter('table_exists')
                    waiter.wait(TableName=self.table_name)
                    
                    logger.info(safe_json_serialize({
                        "Data_Source": "Database_Operations",
                        "Data_Target": "Table_Now_Active",
                        "Data_Artifacts": {
                            "table_name": self.table_name,
                            "action": "table_now_active",
                            "aws_service": "DynamoDB"
                        }
                    }))
                    
                    return True
                else:
                    logger.info(safe_json_serialize({
                        "Data_Source": "Database_Operations",
                        "Data_Target": "Table_Invalid_Status",
                        "Data_Artifacts": {
                            "table_name": self.table_name,
                            "table_status": table_status,
                            "action": "table_invalid_status",
                            "aws_service": "DynamoDB"
                        }
                    }))
                    
                    return False
                    
            except dynamodb_client.exceptions.ResourceNotFoundException:
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Table_Not_Found",
                    "Data_Artifacts": {
                        "table_name": self.table_name,
                        "action": "table_not_found",
                        "aws_service": "DynamoDB"
                    }
                }))
                
                return self.create_table()
                
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Check_Table_Error",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "check_table_error",
                    "aws_service": "DynamoDB"
                }
            }))
            
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
    
    def create_item(self, item_data):
        """
        Create a new item in the DynamoDB table.
        """
        item_id = item_data.get('id', str(uuid.uuid4()))
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Create_Item",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "item_id": item_id,
                "action": "create_item",
                "item_data": item_data
            }
        }))
        
        try:
            # Convert item_data to DynamoDB format
            dynamodb_item = {}
            for key, value in item_data.items():
                if isinstance(value, dict):
                    dynamodb_item[key] = {'S': json.dumps(value)}
                else:
                    dynamodb_item[key] = {'S': str(value)}
            
            response = dynamodb_client.put_item(
                TableName=self.table_name,
                Item=dynamodb_item
            )
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Create_Item_Success",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "item_id": item_id,
                    "action": "create_item_success",
                    "response_metadata": {
                        "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                        "consumed_capacity": response.get('ConsumedCapacity', {})
                    }
                }
            }))
            
            return {
                'status': 'success',
                'item_id': item_id,
                'response': {
                    'consumed_capacity': response.get('ConsumedCapacity', {}),
                    'request_id': response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
                }
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Create_Item_Error",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "item_id": item_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "create_item_error"
                }
            }))
            
            raise
    
    def read_item(self, item_id):
        """
        Read an item from the DynamoDB table.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Read_Item",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "item_id": item_id,
                "action": "read_item",
                "key": {"id": item_id}
            }
        }))
        
        try:
            response = dynamodb_client.get_item(
                TableName=self.table_name,
                Key={'id': {'S': item_id}}
            )
            
            item_found = 'Item' in response
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Read_Item_Result",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "item_id": item_id,
                    "action": "read_item_result",
                    "item_found": item_found,
                    "item_data": response.get('Item', {}),
                    "response_metadata": {
                        "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                        "consumed_capacity": response.get('ConsumedCapacity', {})
                    }
                }
            }))
            
            return {
                'status': 'success' if item_found else 'not_found',
                'item_id': item_id,
                'item_found': item_found,
                'item_data': response.get('Item', {}),
                'response': {
                    'consumed_capacity': response.get('ConsumedCapacity', {}),
                    'request_id': response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
                }
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Read_Item_Error",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "item_id": item_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "read_item_error"
                }
            }))
            
            raise
    
    def update_item(self, item_id, update_data):
        """
        Update an item in the DynamoDB table.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Update_Item",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "item_id": item_id,
                "action": "update_item",
                "update_data": update_data
            }
        }))
        
        try:
            # Build update expression and attributes
            update_expression = "SET "
            expression_attribute_names = {}
            expression_attribute_values = {}
            
            for i, (key, value) in enumerate(update_data.items()):
                attr_name = f"#{key}"
                attr_value = f":{key}"
                
                update_expression += f"{attr_name} = {attr_value}, "
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = {'S': str(value)}
            
            # Remove trailing comma and space
            update_expression = update_expression.rstrip(", ")
            
            response = dynamodb_client.update_item(
                TableName=self.table_name,
                Key={'id': {'S': item_id}},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues='ALL_NEW'
            )
            
            updated_attributes = list(response.get('Attributes', {}).keys())
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Update_Item_Success",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "item_id": item_id,
                    "action": "update_item_success",
                    "updated_attributes": updated_attributes,
                    "new_item_data": response.get('Attributes', {}),
                    "response_metadata": {
                        "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                        "consumed_capacity": response.get('ConsumedCapacity', {})
                    }
                }
            }))
            
            return {
                'status': 'success',
                'item_id': item_id,
                'updated_attributes': updated_attributes,
                'response': {
                    'consumed_capacity': response.get('ConsumedCapacity', {}),
                    'request_id': response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
                }
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Update_Item_Error",
                "Data_Artifacts": {
                    "table_name": self.table_name,
                    "item_id": item_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "update_item_error"
                }
            }))
            
            raise
    
    def delete_item(self, item_id):
        """
        Delete an item from the DynamoDB table (currently skipped for data preservation).
        """
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Delete_Item_Skipped",
            "Data_Artifacts": {
                "table_name": self.table_name,
                "item_id": item_id,
                "action": "delete_item_skipped",
                "reason": "Data preservation requested - keeping items in table",
                "aws_service": "DynamoDB"
            }
        }))
        
        return {
            'status': 'skipped',
            'item_id': item_id,
            'reason': 'Data preservation requested - keeping items in table'
        }
    
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