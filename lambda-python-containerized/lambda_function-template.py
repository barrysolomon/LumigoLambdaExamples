import json
import os
import time
import logging
import requests
import boto3
import uuid
from datetime import datetime
from functools import wraps

# Import the separate API modules
from dynamodb_api import DynamoDBDAL
from s3_api import S3DAL
from api_calls import APIDAL

# =============================================================================
# LUMIGO INSTRUMENTATION HELPERS
# =============================================================================

# from opentelemetry import trace
# from lumigo_opentelemetry import lumigo_wrapped
from lumigo_tracer import lumigo_tracer
from lumigo_tracer import add_execution_tag, error

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# def add_execution_tag(key, value):
#     """
#     Add an execution tag to the current span.
#     Only used for resource names (table names, bucket names, endpoints).
#     """
#     try:
#         span = trace.get_current_span()
#         span.set_attribute(f"lumigo.execution_tags.{key}", str(value))
#         logger.info(f"Added execution tag: {key} = {value}")
#     except Exception as e:
#         logger.error(f"Failed to add execution tag {key}: {str(e)}")

# def add_programmatic_error(error_type, error_message):
#     """
#     Add a programmatic error to the current span.
#     """
#     try:
#         span = trace.get_current_span()
#         span.set_attribute("lumigo.error.type", error_type)
#         span.set_attribute("lumigo.error.message", error_message)
#         logger.error(f"Added programmatic error: {error_type} - {error_message}")
#     except Exception as e:
#         logger.error(f"Failed to add programmatic error: {str(e)}")

def add_programmatic_error(error_type, error_message):
    """
    Add a programmatic error using Lumigo tracer.
    Based on https://docs.lumigo.io/docs/programmatic-errors
    """
    try:
        error(error_message, error_type)
        logger.error(f"Added programmatic error: {error_type} - {error_message}")
    except Exception as e:
        logger.error(f"Failed to add programmatic error: {str(e)}")

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

def perform_s3_operations():
    """
    Example: Wrap existing S3 operations with Lumigo instrumentation.
    This is how clients would instrument their existing S3 calls.
    """
    try:
        # Create DAL instance
        dal = S3DAL()
        
        # Add execution tag for S3 bucket
        add_execution_tag("s3_bucket", dal.bucket_name)
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "S3_Operations",
            "Data_Artifacts": {
                "bucket_name": dal.bucket_name,
                "aws_service": "S3",
                "action": "s3_operations_start",
                "service": "S3_API"
            }
        }))
        
        # Check if bucket exists and create if needed
        bucket_ready = dal.ensure_bucket_exists()
        
        if bucket_ready:
            # Generate unique identifiers for this operation
            operation_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Lifecycle_Operations_Start",
                "Data_Artifacts": {
                    "bucket_name": dal.bucket_name,
                    "operation_id": operation_id,
                    "timestamp": timestamp,
                    "action": "lifecycle_operations_start",
                    "service": "S3_API"
                }
            }))
            
            try:
                # Step 1: Upload sample objects (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Upload_Objects",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "action": "upload_objects_start",
                        "service": "S3_API"
                    }
                }))
                
                upload_results = dal.upload_sample_objects(operation_id, timestamp)
                objects_created = upload_results.get('objects_created', 0)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Upload_Objects_Complete",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "objects_created": objects_created,
                        "action": "upload_objects_complete",
                        "service": "S3_API"
                    }
                }))
                
                # Step 2: List objects in the bucket (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "List_Objects",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "action": "list_objects_start",
                        "service": "S3_API"
                    }
                }))
                
                list_results = dal.list_bucket_objects(operation_id)
                object_count = list_results.get('object_count', 0)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "List_Objects_Complete",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "object_count": object_count,
                        "action": "list_objects_complete",
                        "service": "S3_API"
                    }
                }))
                
                # Step 3: Delete the objects we created (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Delete_Objects",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "action": "delete_objects_start",
                        "service": "S3_API"
                    }
                }))
                
                delete_results = dal.delete_bucket_objects(operation_id)
                objects_deleted = delete_results.get('objects_deleted', 0)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Delete_Objects_Complete",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "objects_deleted": objects_deleted,
                        "action": "delete_objects_complete",
                        "service": "S3_API"
                    }
                }))
                
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Lifecycle_Operations_Complete",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "objects_created": objects_created,
                        "objects_deleted": objects_deleted,
                        "action": "lifecycle_operations_complete",
                        "service": "S3_API"
                    }
                }))
                
                return {
                    'bucket_used': dal.bucket_name,
                    'objects_created': objects_created,
                    'objects_deleted': objects_deleted
                }
                
            except Exception as e:
                logger.error(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Lifecycle_Operations_Error",
                    "Data_Artifacts": {
                        "bucket_name": dal.bucket_name,
                        "operation_id": operation_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "action": "lifecycle_operations_error",
                        "service": "S3_API"
                    }
                }))
                raise
        else:
            logger.error(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Bucket_Setup_Error",
                "Data_Artifacts": {
                    "bucket_name": dal.bucket_name,
                    "error": "Failed to setup bucket",
                    "action": "bucket_setup_error",
                    "service": "S3_API"
                }
            }))
            return {
                'bucket_used': dal.bucket_name,
                'status': 'bucket_setup_failed'
            }
            
    except Exception as e:
        logger.error(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "S3_Operations_Error",
            "Data_Artifacts": {
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "s3_operations_error",
                "service": "S3_API"
            }
        }))
        return {
            'bucket_used': 'unknown',
            'status': 'error',
            'error': str(e)
        }

def perform_api_operations():
    """
    Example: Wrap existing API operations with Lumigo instrumentation.
    This is how clients would instrument their existing API calls.
    """
    try:
        # Create DAL instance
        dal = APIDAL()
        
        # Round-robin through API endpoints
        api_endpoints = [
            "https://jsonplaceholder.typicode.com/posts/1",
            "https://jsonplaceholder.typicode.com/posts/2", 
            "https://jsonplaceholder.typicode.com/posts/3"
        ]
        endpoint_index = (int(time.time()) % len(api_endpoints))
        endpoint = api_endpoints[endpoint_index]
        
        # Add execution tag for API URL
        add_execution_tag("api_url", endpoint)
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "API_Operations",
            "Data_Artifacts": {
                "endpoint": endpoint,
                "round_robin_index": endpoint_index,
                "action": "api_operations_start",
                "service": "JSONPlaceholder_API"
            }
        }))
        
        # Make the API call (wrapped service call)
        response = dal.fetch_data(endpoint)
        
        logger.info(safe_json_serialize({
            "Data_Source": "API_Operations",
            "Data_Target": "API_Call_Complete",
            "Data_Artifacts": {
                "endpoint": endpoint,
                "status_code": response['status_code'],
                "response_time": response['response_time'],
                "post_id": response['data'].get('id'),
                "post_title": response['data'].get('title'),
                "action": "api_call_complete",
                "service": "JSONPlaceholder_API"
            }
        }))
        
        return {
            'endpoint_used': endpoint,
            'post_id': response['data'].get('id'),
            'post_title': response['data'].get('title'),
            'status_code': response['status_code'],
            'response_time': response['response_time']
        }
        
    except Exception as e:
        logger.error(safe_json_serialize({
            "Data_Source": "API_Operations",
            "Data_Target": "API_Error",
            "Data_Artifacts": {
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "api_operations_error",
                "service": "JSONPlaceholder_API"
            }
        }))
        return {
            'endpoint_used': 'unknown',
            'status': 'error',
            'error': str(e)
        }

def perform_database_operations(table_name=None):
    """
    Example: Wrap existing DynamoDB operations with Lumigo instrumentation.
    This is how clients would instrument their existing DynamoDB calls.
    """
    try:
        # Create DAL instance
        dal = DynamoDBDAL(table_name)
        
        # Add execution tags for database and table
        add_execution_tag("database", "DynamoDB")
        add_execution_tag("database_table", dal.table_name)
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "Database_Operations",
            "Data_Artifacts": {
                "table_name": dal.table_name,
                "aws_service": "DynamoDB",
                "action": "database_operations_start",
                "service": "DynamoDB_API"
            }
        }))
        
        # Ensure table exists
        table_ready = dal.ensure_table_exists()
        
        if table_ready:
            # Generate unique item ID
            item_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "CRUD_Operations_Start",
                "Data_Artifacts": {
                    "table_name": dal.table_name,
                    "item_id": item_id,
                    "timestamp": timestamp,
                    "action": "crud_operations_start",
                    "service": "DynamoDB_API"
                }
            }))
            
            try:
                # Step 1: Create item (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Create_Item",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "create_item_start",
                        "service": "DynamoDB_API"
                    }
                }))
                
                item_data = {
                    'id': {'S': item_id},
                    'data': {'S': 'Sample data'},
                    'timestamp': {'S': timestamp},
                    'status': {'S': 'active'}
                }
                create_response = dal.create_item(item_data)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Create_Item_Complete",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "create_item_complete",
                        "service": "DynamoDB_API"
                    }
                }))
                
                # Step 2: Read item (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Read_Item",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "read_item_start",
                        "service": "DynamoDB_API"
                    }
                }))
                
                read_response = dal.read_item(item_id)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Read_Item_Complete",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "read_item_complete",
                        "service": "DynamoDB_API"
                    }
                }))
                
                # Step 3: Update item (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Update_Item",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "update_item_start",
                        "service": "DynamoDB_API"
                    }
                }))
                
                updates = {
                    'status': 'updated',
                    'updated_at': timestamp
                }
                update_response = dal.update_item(item_id, updates)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Update_Item_Complete",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "update_item_complete",
                        "service": "DynamoDB_API"
                    }
                }))
                
                # Step 4: Delete item (wrapped service call)
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Delete_Item",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "delete_item_start",
                        "service": "DynamoDB_API"
                    }
                }))
                
                delete_response = dal.delete_item(item_id)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Delete_Item_Complete",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "action": "delete_item_complete",
                        "service": "DynamoDB_API"
                    }
                }))
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "CRUD_Operations_Complete",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "operations_count": 4,
                        "action": "crud_operations_complete",
                        "service": "DynamoDB_API"
                    }
                }))
                
                return {
                    'table_used': dal.table_name,
                    'operations_count': 4,
                    'item_id': item_id
                }
                
            except Exception as e:
                logger.error(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "CRUD_Operations_Error",
                    "Data_Artifacts": {
                        "table_name": dal.table_name,
                        "item_id": item_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "action": "crud_operations_error",
                        "service": "DynamoDB_API"
                    }
                }))
                raise
        else:
            logger.error(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Table_Setup_Error",
                "Data_Artifacts": {
                    "table_name": dal.table_name,
                    "error": "Failed to setup table",
                    "action": "table_setup_error",
                    "service": "DynamoDB_API"
                }
            }))
            return {
                'table_used': dal.table_name,
                'status': 'table_setup_failed'
            }
            
    except Exception as e:
        logger.error(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Database_Operations_Error",
            "Data_Artifacts": {
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "database_operations_error",
                "service": "DynamoDB_API"
            }
        }))
        return {
            'table_used': 'unknown',
            'status': 'error',
            'error': str(e)
        }

# =============================================================================
# MAIN LAMBDA HANDLER
# =============================================================================

#@lumigo_wrapped
@lumigo_tracer()
def lambda_handler(event, context):
    """
    Example Lambda function showing how to wrap existing code with Lumigo instrumentation.
    This demonstrates how clients can easily instrument their existing database, S3, and API calls.
    """
    try:
        
        # Log the incoming event
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Event",
            "Data_Target": "Lambda_Handler",
            "Data_Artifacts": {
                "event": event,
                "request_id": context.aws_request_id
            }
        }))
        
        # API calls
        try:
            api_data = perform_api_operations()
        except Exception as e:
            add_programmatic_error("API_OPERATION_FAILED", str(e), {
                "error_type": type(e).__name__
            })
            api_data = {'error': str(e)}
        
        # S3 operations 
        try:
            s3_data = perform_s3_operations()
        except Exception as e:
            add_programmatic_error("S3_OPERATION_FAILED", str(e), {
                "error_type": type(e).__name__
            })
            s3_data = {'error': str(e)}
        
        # DynamoDB operations
        try:
            db_data = perform_database_operations()
        except Exception as e:
            add_programmatic_error("DATABASE_OPERATION_FAILED", str(e), {
                "error_type": type(e).__name__
            })
            db_data = {'error': str(e)}
        
        # Simulate some processing
        result = None
        if 'data' in event:
            processed_data = event['data'].upper()
            result = f"Processed: {processed_data}"
        else:
            result = "No data to process"
    
        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Lambda function executed successfully',
                'api_data': api_data,
                's3_data': s3_data,
                'db_data': db_data,
                'result': result,
                'request_id': context.aws_request_id
            })
        }
        
    except requests.RequestException as e:
        # Wrap HTTP errors with Lumigo programmatic errors
        error_message = f"HTTP request failed: {str(e)}"
        logger.info(safe_json_serialize({
            "Data_Source": "HTTP_Request",
            "Data_Target": "Error_Handling",
            "Data_Artifacts": {
                "error_message": error_message,
                "error_type": type(e).__name__
            }
        }))
        
        add_programmatic_error("HTTP_REQUEST_FAILED", error_message, {
            "error_code": getattr(e.response, 'status_code', 'unknown') if hasattr(e, 'response') else 'unknown'
        })
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message,
                'request_id': context.aws_request_id
            })
        }
        
    except Exception as e:
        # Wrap general errors with Lumigo programmatic errors
        error_message = f"Lambda execution failed: {str(e)}"
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Execution",
            "Data_Target": "Error_Handling",
            "Data_Artifacts": {
                "error_message": error_message,
                "error_type": type(e).__name__,
                "function_name": context.function_name,
                "request_id": context.aws_request_id
            }
        }))
        
        add_programmatic_error("LAMBDA_EXECUTION_FAILED", error_message, {
            "error_type": type(e).__name__,
            "function_name": context.function_name,
            "request_id": context.aws_request_id
        })
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message,
                'request_id': context.aws_request_id
            })
        }
