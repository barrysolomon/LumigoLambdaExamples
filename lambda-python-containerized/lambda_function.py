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

from opentelemetry import trace
from lumigo_opentelemetry import lumigo_wrapped

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def add_execution_tag(key, value):
    """
    Add an execution tag to the current span.
    Execution tags help identify, search for, and filter invocations in Lumigo.
    """
    try:
        # Use the correct OpenTelemetry API
        active_span = trace.get_current_span()
        if active_span:
            # Add the lumigo.execution_tags prefix as required by Lumigo
            active_span.set_attribute(f"lumigo.execution_tags.{key}", str(value))
            logger.info(f"Added execution tag: {key} = {value}")
    except Exception as e:
        logger.info(f"Failed to add execution tag {key}: {str(e)}")

def add_programmatic_error(error_type, error_message, error_attributes=None):
    """
    Add a programmatic error to the current span.
    This helps Lumigo identify and categorize errors for better monitoring.
    
    Args:
        error_type (str): The type/category of the error (e.g., "HTTP_REQUEST_FAILED")
        error_message (str): The error message
        error_attributes (dict): Additional attributes to include with the error
    """
    try:
        active_span = trace.get_current_span()
        if active_span:
            # Add error attributes to the span
            active_span.set_attribute("lumigo.error.type", error_type)
            active_span.set_attribute("lumigo.error.message", error_message)
            
            # Add additional error attributes if provided
            if error_attributes:
                for key, value in error_attributes.items():
                    active_span.set_attribute(f"lumigo.error.{key}", str(value))
            
            # Mark the span as having an error
            active_span.set_attribute("lumigo.error", "true")
            
            logger.info(f"Added programmatic error: {error_type} - {error_message}")
            
    except Exception as e:
        logger.info(f"Failed to add programmatic error {error_type}: {str(e)}")

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

def log_call_params(service_name):
    """
    Decorator to log function call parameters.
    
    Args:
        service_name (str): Name of the service (e.g., "S3", "Database", "API")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract key parameters for logging
            params = {}
            
            # Look for common parameter names
            if 'table_name' in kwargs:
                params['table_name'] = kwargs['table_name']
            if 'bucket_name' in kwargs:
                params['bucket_name'] = kwargs['bucket_name']
            if 'endpoint' in kwargs:
                params['endpoint'] = kwargs['endpoint']
            
            # Log the call with parameters
            if params:
                param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                logger.info(f"{service_name} Call - {func.__name__} with params: {param_str}")
            else:
                logger.info(f"{service_name} Call - {func.__name__}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

@log_call_params("S3")
def perform_s3_operations():
    """
    Example: Wrap existing S3 operations with Lumigo instrumentation.
    This is how clients would instrument their existing S3 calls.
    """
    try:
        # Create DAL instance
        dal = S3DAL()
        
        # Log bucket information
        logger.info(f"S3 Operations - Using bucket: {dal.bucket_name}")
        
        # Check if bucket exists and create if needed
        bucket_ready = dal.ensure_bucket_exists()
        
        if bucket_ready:
            # Generate unique identifiers for this operation
            operation_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            logger.info(f"S3 Lifecycle Operations - Starting with operation_id: {operation_id}")
            
            try:
                # Step 1: Upload sample objects
                logger.info(f"S3 Upload - Starting upload to bucket: {dal.bucket_name}")
                upload_results = dal.upload_sample_objects(operation_id, timestamp)
                objects_created = upload_results.get('objects_created', 0)
                logger.info(f"S3 Upload - Completed. Objects created: {objects_created}")
                
                # Step 2: List objects in the bucket
                logger.info(f"S3 List - Listing objects in bucket: {dal.bucket_name}")
                list_results = dal.list_bucket_objects(operation_id)
                object_count = list_results.get('object_count', 0)
                logger.info(f"S3 List - Completed. Objects found: {object_count}")
                
                # Step 3: Delete the objects we created
                logger.info(f"S3 Delete - Starting deletion from bucket: {dal.bucket_name}")
                delete_results = dal.delete_bucket_objects(operation_id)
                objects_deleted = delete_results.get('objects_deleted', 0)
                logger.info(f"S3 Delete - Completed. Objects deleted: {objects_deleted}")
                
                logger.info(f"S3 Lifecycle Operations - Completed successfully")
                
                return {
                    'bucket_used': dal.bucket_name,
                    'objects_created': objects_created,
                    'objects_deleted': objects_deleted
                }
                
            except Exception as e:
                logger.error(f"S3 Lifecycle Operations - Failed: {str(e)}")
                raise
        else:
            logger.error(f"S3 Setup - Failed to setup bucket: {dal.bucket_name}")
            return {
                'bucket_used': dal.bucket_name,
                'status': 'bucket_setup_failed'
            }
            
    except Exception as e:
        logger.error(f"S3 Operations - Error: {str(e)}")
        return {
            'error': str(e)
        }

@log_call_params("API")
def perform_api_operations():
    """
    Example: Wrap existing API calls with Lumigo instrumentation.
    This is how clients would instrument their existing HTTP requests.
    """
    try:
        # Create DAL instance
        dal = APIDAL()
        
        # Log API endpoint information
        logger.info(f"API Operations - Using endpoint: {dal.endpoint}")
        
        # Perform API operations using DAL
        logger.info(f"API Request - Making request to: {dal.endpoint}")
        api_results = dal.fetch_data()
        
        logger.info(f"API Request - Completed successfully")
        
        return {
            'endpoint_used': dal.endpoint,
            'post_id': api_results.get('post_id'),
            'post_title': api_results.get('post_title'),
            'status_code': api_results.get('status_code'),
            'response_time': api_results.get('response_time')
        }
        
    except Exception as e:
        logger.error(f"API Operations - Error: {str(e)}")
        return {
            'error': str(e)
        }

@log_call_params("Database")
def perform_database_operations(table_name=None):
    """
    Example: Wrap existing DynamoDB operations with Lumigo instrumentation.
    This is how clients would instrument their existing database calls.
    
    Args:
        table_name (str, optional): Specific table name to use. If None, uses round-robin selection.
    """
    try:
        # Create DAL instance with optional table name
        dal = DynamoDBDAL(table_name=table_name)
        
        # Log table information
        logger.info(f"Database Operations - Using table: {dal.table_name}")
        
        # Check if table exists and create if needed
        table_ready = dal.ensure_table_exists()
        
        if table_ready:
            # Generate a unique item ID for this operation
            item_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()
            
            logger.info(f"Database CRUD Operations - Starting with item_id: {item_id}")
            
            try:
                # CREATE operation
                logger.info(f"Database CREATE - Creating item in table: {dal.table_name}")
                item_data = {
                    'id': item_id,
                    'timestamp': timestamp,
                    'data': 'Sample data for CRUD demonstration',
                    'status': 'active',
                    'metadata': {'created_by': 'lambda-function', 'version': '1.0'}
                }
                
                create_result = dal.create_item(item_data)
                logger.info(f"Database CREATE - Completed successfully")
                
                # READ operation
                logger.info(f"Database READ - Reading item from table: {dal.table_name}")
                read_result = dal.read_item(item_id)
                logger.info(f"Database READ - Completed successfully")
                
                # UPDATE operation
                logger.info(f"Database UPDATE - Updating item in table: {dal.table_name}")
                update_data = {
                    'status': 'updated',
                    'updated_at': datetime.utcnow().isoformat()
                }
                
                update_result = dal.update_item(item_id, update_data)
                logger.info(f"Database UPDATE - Completed successfully")
                
                # DELETE operation (skipped)
                logger.info(f"Database DELETE - Skipping delete for data preservation")
                delete_result = dal.delete_item(item_id)
                logger.info(f"Database DELETE - Skipped successfully")
                
                logger.info(f"Database CRUD Operations - Completed successfully")
                
                return {
                    'table_used': dal.table_name,
                    'operations_count': 4,
                    'item_id': item_id
                }
                
            except Exception as e:
                logger.error(f"Database CRUD Operations - Failed: {str(e)}")
                raise
        else:
            logger.error(f"Database Setup - Failed to setup table: {dal.table_name}")
            return {
                'table_used': dal.table_name,
                'status': 'table_setup_failed'
            }
            
    except Exception as e:
        logger.error(f"Database Operations - Error: {str(e)}")
        return {
            'error': str(e)
        }

# =============================================================================
# MAIN LAMBDA HANDLER
# =============================================================================
@lumigo_wrapped
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



