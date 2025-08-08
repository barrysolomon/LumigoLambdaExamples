import json
import os
import time
import logging
import requests
import boto3
import uuid
import random
import signal
from datetime import datetime
from functools import wraps

# Import the separate API modules
from dynamodb_api import DynamoDBDAL
from s3_api import S3DAL
from api_calls import APIDAL
from postgresql_api import PostgreSQLDAL

# =============================================================================
# LUMIGO INSTRUMENTATION HELPERS
# =============================================================================

from lumigo_tracer import lumigo_tracer
from lumigo_tracer import add_execution_tag, error

def timeout_handler(signum, frame):
    """Handle timeout signal"""
    raise TimeoutError("Operation timed out")

def timeout(seconds):
    """Decorator to add timeout to functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Set the signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return result
        return wrapper
    return decorator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

@timeout(30)  # 30 second timeout for RDS operations
def perform_rds_operations():
    """
    Example: Wrap existing RDS PostgreSQL operations with Lumigo instrumentation.
    This is how clients would instrument their existing RDS PostgreSQL calls.
    """
    try:
        # Create DAL instance
        dal = PostgreSQLDAL()
        
        # Add execution tags for database and table
        add_execution_tag("database", "RDS_PostgreSQL")
        add_execution_tag("database_table", dal.table_name)
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "RDS_Operations",
            "Data_Artifacts": {
                "database_type": "RDS_PostgreSQL",
                "table_name": dal.table_name,
                "aws_service": "RDS",
                "action": "rds_operations_start",
                "service": "RDS_PostgreSQL_API"
            }
        }))
        
        # Quick check if RDS is accessible (fail fast)
        if not dal.connection_available:
            logger.warning("⚠️  RDS not available, skipping operations")
            return {
                'database_type': 'RDS_PostgreSQL',
                'table_used': 'unknown',
                'status': 'skipped',
                'message': 'RDS connection not available'
            }
        
        # Ensure table exists (with timeout)
        table_ready = dal.ensure_table_exists()
        
        if table_ready:
            # Generate unique user ID
            user_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            logger.info(safe_json_serialize({
                "Data_Source": "RDS_Operations",
                "Data_Target": "CRUD_Operations_Start",
                "Data_Artifacts": {
                    "database_type": "RDS_PostgreSQL",
                    "table_name": dal.table_name,
                    "user_id": user_id,
                    "timestamp": timestamp,
                    "action": "rds_crud_operations_start",
                    "service": "RDS_PostgreSQL_API"
                }
            }))
            
            try:
                # Step 1: Insert operations (wrapped service calls)
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Insert_Operations",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "action": "insert_operations_start",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                # Insert user
                user_data = {
                    'id': user_id,
                    'username': f'user_{random.randint(1000, 9999)}',
                    'email': f'user_{random.randint(1000, 9999)}@example.com',
                    'created_at': timestamp,
                    'status': 'active'
                }
                create_user_response = dal.create_user(user_data)
                
                # Insert product
                product_id = str(uuid.uuid4())
                product_data = {
                    'id': product_id,
                    'name': f'Product_{random.randint(100, 999)}',
                    'price': round(random.uniform(10.0, 1000.0), 2),
                    'category': random.choice(['Electronics', 'Clothing', 'Books', 'Home']),
                    'created_at': timestamp
                }
                create_product_response = dal.insert_product(product_data)
                
                # Insert order
                order_id = str(uuid.uuid4())
                order_data = {
                    'id': order_id,
                    'user_id': user_id,
                    'total_amount': round(random.uniform(50.0, 500.0), 2),
                    'status': 'pending',
                    'created_at': timestamp
                }
                create_order_response = dal.insert_order(order_data)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Insert_Operations_Complete",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "inserts_completed": 3,
                        "user_id": user_id,
                        "product_id": product_id,
                        "order_id": order_id,
                        "action": "insert_operations_complete",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                # Step 2: Read operations (wrapped service calls)
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Read_Operations",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "action": "read_operations_start",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                read_user_response = dal.read_user(user_id)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Read_Operations_Complete",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "user_id": user_id,
                        "user_found": read_user_response.get('user_found', False),
                        "action": "read_operations_complete",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                # Step 3: Update operations (wrapped service calls)
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Update_Operations",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "action": "update_operations_start",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                # Update user
                user_updates = {
                    'status': 'updated',
                    'updated_at': timestamp,
                    'last_login': timestamp
                }
                update_user_response = dal.update_user(user_id, user_updates)
                
                # Update product
                product_updates = {
                    'price': round(random.uniform(10.0, 1000.0), 2),
                    'updated_at': timestamp
                }
                update_product_response = dal.update_product(product_id, product_updates)
                
                # Update order status
                update_order_response = dal.update_order_status(order_id, 'processing')
                
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Update_Operations_Complete",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "updates_completed": 3,
                        "user_id": user_id,
                        "product_id": product_id,
                        "order_id": order_id,
                        "action": "update_operations_complete",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                # Step 4: Delete operations (wrapped service calls)
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Delete_Operations",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "action": "delete_operations_start",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                # Delete order
                delete_order_response = dal.delete_order(order_id)
                
                # Delete product
                delete_product_response = dal.delete_product(product_id)
                
                # Delete user
                delete_user_response = dal.delete_user(user_id)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "Delete_Operations_Complete",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "deletes_completed": 3,
                        "user_id": user_id,
                        "product_id": product_id,
                        "order_id": order_id,
                        "action": "delete_operations_complete",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                logger.info(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "CRUD_Operations_Complete",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "user_id": user_id,
                        "product_id": product_id,
                        "order_id": order_id,
                        "total_operations": 12,
                        "inserts": 3,
                        "reads": 1,
                        "updates": 3,
                        "deletes": 3,
                        "action": "rds_crud_operations_complete",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                
                return {
                    'database_type': 'RDS_PostgreSQL',
                    'table_used': dal.table_name,
                    'operations_count': 12,
                    'user_id': user_id,
                    'product_id': product_id,
                    'order_id': order_id,
                    'status': 'success'
                }
                
            except Exception as e:
                logger.error(safe_json_serialize({
                    "Data_Source": "RDS_Operations",
                    "Data_Target": "CRUD_Operations_Error",
                    "Data_Artifacts": {
                        "database_type": "RDS_PostgreSQL",
                        "table_name": dal.table_name,
                        "user_id": user_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "action": "rds_crud_operations_error",
                        "service": "RDS_PostgreSQL_API"
                    }
                }))
                raise
        else:
            logger.error(safe_json_serialize({
                "Data_Source": "RDS_Operations",
                "Data_Target": "Table_Setup_Error",
                "Data_Artifacts": {
                    "database_type": "RDS_PostgreSQL",
                    "table_name": dal.table_name,
                    "error": "Failed to setup table",
                    "action": "table_setup_error",
                    "service": "RDS_PostgreSQL_API"
                }
            }))
            return {
                'database_type': 'RDS_PostgreSQL',
                'table_used': dal.table_name,
                'status': 'table_setup_failed'
            }
            
    except TimeoutError as e:
        logger.error(safe_json_serialize({
            "Data_Source": "RDS_Operations",
            "Data_Target": "RDS_Operations_Timeout",
            "Data_Artifacts": {
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "rds_operations_timeout",
                "service": "RDS_PostgreSQL_API"
            }
        }))
        add_programmatic_error("RDS_TIMEOUT_ERROR", f"RDS operations timed out: {str(e)}")
        return {
            'database_type': 'RDS_PostgreSQL',
            'table_used': 'unknown',
            'status': 'timeout',
            'error': str(e)
        }
    except Exception as e:
        logger.error(safe_json_serialize({
            "Data_Source": "RDS_Operations",
            "Data_Target": "RDS_Operations_Error",
            "Data_Artifacts": {
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "rds_operations_error",
                "service": "RDS_PostgreSQL_API"
            }
        }))
        add_programmatic_error("RDS_OPERATION_ERROR", f"RDS operations failed: {str(e)}")
        return {
            'database_type': 'RDS_PostgreSQL',
            'table_used': 'unknown',
            'status': 'error',
            'error': str(e)
        }

# =============================================================================
# MAIN LAMBDA HANDLER
# =============================================================================

@lumigo_tracer()
def lambda_handler(event, context):
    """
    Example Lambda function showing how to wrap existing code with Lumigo instrumentation.
    This demonstrates how clients can easily instrument their existing database, S3, and API calls.
    """
    try:
        
        add_execution_tag("username", "surandra")   

        # Get actions from event (default to all true if not specified)
        actions = event.get('actions', {
            'api_operations': True,
            's3_operations': True,
            'database_operations': True,
            'rds_operations': True
        })

        # Log the incoming event
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Event",
            "Data_Target": "Lambda_Handler",
            "Data_Artifacts": {
                "event": event,
                "actions": actions,
                "request_id": context.aws_request_id
            }
        }))
        
        # Initialize response data
        api_data = {'skipped': True, 'reason': 'api_operations disabled'}
        s3_data = {'skipped': True, 'reason': 's3_operations disabled'}
        db_data = {'skipped': True, 'reason': 'database_operations disabled'}
        rds_data = {'skipped': True, 'reason': 'rds_operations disabled'}
        
        # API calls
        if actions.get('api_operations', True):
            try:
                api_data = perform_api_operations()
            except Exception as e:
                add_programmatic_error("API_OPERATION_FAILED", str(e), {
                    "error_type": type(e).__name__
                })
                api_data = {'error': str(e)}
        
        # S3 operations 
        if actions.get('s3_operations', True):
            try:
                s3_data = perform_s3_operations()
            except Exception as e:
                add_programmatic_error("S3_OPERATION_FAILED", str(e), {
                    "error_type": type(e).__name__
                })
                s3_data = {'error': str(e)}
        
        # DynamoDB operations
        if actions.get('database_operations', True):
            try:
                db_data = perform_database_operations()
            except Exception as e:
                add_programmatic_error("DATABASE_OPERATION_FAILED", str(e), {
                    "error_type": type(e).__name__
                })
                db_data = {'error': str(e)}
        
        # RDS PostgreSQL operations
        if actions.get('rds_operations', True):
            try:
                rds_data = perform_rds_operations()
            except TimeoutError as e:
                add_programmatic_error("RDS_TIMEOUT_FAILED", str(e), {
                    "error_type": type(e).__name__
                })
                rds_data = {'error': str(e), 'timeout': True}
            except Exception as e:
                add_programmatic_error("RDS_OPERATION_FAILED", str(e), {
                    "error_type": type(e).__name__
                })
                rds_data = {'error': str(e)}
        
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
                'rds_data': rds_data,
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

# =============================================================================
# LOCAL TESTING SECTION
# =============================================================================

if __name__ == "__main__":
    """
    Local testing with optional AWS services.
    Run with: python lambda_function.py
    """
    import json
    import os
    import boto3
    
    # Set up mock environment for local testing
    os.environ['OTEL_SERVICE_NAME'] = 'lambda-python-lumigo-local'
    os.environ['LUMIGO_TRACER_TOKEN'] = 'local-test-token'
    os.environ['LUMIGO_ENABLE_LOGS'] = 'true'
    os.environ['DYNAMODB_TABLE_NAME'] = 'example-table'
    os.environ['S3_BUCKET_NAME'] = 'example-bucket'
    
    # Check if AWS credentials are available
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        aws_available = True
        print(f"✅ AWS credentials available - Account: {identity['Account']}")
    except Exception as e:
        aws_available = False
        print(f"⚠️  AWS credentials not available: {str(e)}")
        print("   Function will run with mock AWS services")
    
    # Mock event for local testing
    test_event = {
        "data": "hello world from lumigo local test",
        "test": True,
        "timestamp": "2024-01-01T00:00:00Z",
        "user_id": "user123",
        "request_type": "local_test",
        "source": "local-python-script"
    }
    
    # Mock context for local testing
    class MockContext:
        def __init__(self):
            self.function_name = "lambda-python-lumigo-local"
            self.function_version = "$LATEST"
            self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:lambda-python-lumigo-local"
            self.memory_limit_in_mb = 512
            self.remaining_time_in_millis = lambda: 30000
            self.aws_request_id = "local-test-request-id"
    
    print("🧪 Local Testing Mode")
    print("=" * 50)
    if aws_available:
        print("Testing Lambda function locally WITH AWS services...")
    else:
        print("Testing Lambda function locally WITHOUT AWS services...")
    print("")
    
    try:
        # Call the lambda handler
        result = lambda_handler(test_event, MockContext())
        
        print("✅ Local test completed successfully!")
        print("")
        print("📄 Response:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Local test failed: {str(e)}")
        print("")
        if not aws_available:
            print("💡 Note: This is expected if the function tries to access AWS services.")
            print("   The function is designed to run in AWS Lambda with proper credentials.")
    
    print("")
    print("🔗 To test with AWS services:")
    print("   - Use ./deploy-containerized.sh (containerized)")
    print("   - Use ./deploy-direct.sh (direct deployment)")
    print("   - Or invoke via AWS CLI after deployment")
