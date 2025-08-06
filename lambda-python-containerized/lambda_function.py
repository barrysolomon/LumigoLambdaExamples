import json
import os
import time
import logging
import requests
import boto3
from datetime import datetime
from opentelemetry import trace
from lumigo_opentelemetry import lumigo_wrapped

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# =============================================================================
# AWS CLIENT INITIALIZATION
# =============================================================================
s3_client = boto3.client('s3')
dynamodb_client = boto3.client('dynamodb')

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
        
        # SECTION 1: Wrap existing API calls with Lumigo instrumentation
        api_data = perform_api_operations()
        
        # SECTION 2: Wrap existing S3 operations with Lumigo instrumentation
        s3_data = perform_s3_operations()
        
        # SECTION 3: Wrap existing DynamoDB operations with Lumigo instrumentation
        db_data = perform_database_operations()
        
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

# =============================================================================
# COMPONENT 1: API OPERATIONS
# =============================================================================
def perform_api_operations():
    """
    Example: Wrap existing API calls with Lumigo instrumentation.
    This is how clients would instrument their existing HTTP requests.
    """
    # Round-robin through API endpoints
    api_endpoints = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2", 
        "https://jsonplaceholder.typicode.com/posts/3"
    ]
    api_index = (int(time.time()) % len(api_endpoints))
    selected_endpoint = api_endpoints[api_index]
    
    # Add execution tag for API endpoint
    add_execution_tag("api_endpoint", selected_endpoint)
    
    logger.info(safe_json_serialize({
        "Data_Source": "Lambda_Handler",
        "Data_Target": "API_Operations",
        "Data_Artifacts": {
            "endpoint": selected_endpoint,
            "method": "GET",
            "service": "JSONPlaceholder_API",
            "round_robin_index": api_index
        }
    }))
    
    try:
        # Existing API operations (client's existing code)
        api_results = fetch_api_data(selected_endpoint)
        

        
        return {
            'endpoint_used': selected_endpoint,
            'post_id': api_results.get('post_id'),
            'post_title': api_results.get('post_title')
        }
        
    except Exception as e:
        # Wrap API errors with Lumigo programmatic errors
        logger.info(safe_json_serialize({
            "Data_Source": "API_Operations",
            "Data_Target": "Error_Handling",
            "Data_Artifacts": {
                "error": str(e),
                "endpoint": selected_endpoint,
                "round_robin_index": api_index
            }
        }))
    
        add_programmatic_error("API_OPERATION_FAILED", str(e), {
            "endpoint": selected_endpoint,
            "error_type": type(e).__name__
        })
        
        return {
            'endpoint_used': selected_endpoint,
            'error': str(e)
        }

def fetch_api_data(endpoint):
    """
    Fetch data from external API endpoint.
    This demonstrates how to track API operations with execution tags.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "External_API",
        "Data_Target": "JSONPlaceholder",
        "Data_Artifacts": {
            "endpoint": endpoint,
            "method": "GET",
            "timeout": 10,
            "action": "fetch_api_data_start",
            "service": "JSONPlaceholder_API"
        }
    }))
    
    # Existing API call (client's existing code)
    response = requests.get(endpoint, timeout=10)
    
    logger.info(safe_json_serialize({
        "Data_Source": "External_API",
        "Data_Target": "API_Response_Received",
        "Data_Artifacts": {
            "endpoint": endpoint,
            "method": "GET",
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None,
            "content_length": len(response.content),
            "headers": dict(response.headers),
            "action": "api_response_received",
            "service": "JSONPlaceholder_API"
        }
    }))
    
    response.raise_for_status()
    post_data = response.json()
    
    logger.info(safe_json_serialize({
        "Data_Source": "External_API",
        "Data_Target": "API_Data_Parsed",
        "Data_Artifacts": {
            "endpoint": endpoint,
            "post_id": post_data.get('id'),
            "post_title": post_data.get('title'),
            "post_body": post_data.get('body', ''),
            "user_id": post_data.get('userId'),
            "parsed_data_keys": list(post_data.keys()),
            "action": "api_data_parsed",
            "service": "JSONPlaceholder_API"
        }
    }))
    

    
    logger.info(safe_json_serialize({
        "Data_Source": "JSONPlaceholder",
        "Data_Target": "Lambda_Handler",
        "Data_Artifacts": {
            "endpoint": endpoint,
            "post_id": post_data.get('id'),
            "post_title": post_data.get('title'),
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None,
            "action": "api_call_complete",
            "service": "JSONPlaceholder_API"
        }
    }))
    
    return {
        'post_id': post_data.get('id'),
        'post_title': post_data.get('title'),
        'endpoint_used': endpoint
    }

# =============================================================================
# COMPONENT 2: S3 OPERATIONS
# =============================================================================
def perform_s3_operations():
    """
    Example: Wrap existing S3 operations with Lumigo instrumentation.
    This is how clients would instrument their existing S3 calls.
    """
    # Round-robin through S3 buckets
    s3_buckets = [
        os.environ.get('S3_BUCKET_NAME', 'example-bucket'),
        os.environ.get('S3_BUCKET_NAME', 'example-bucket') + '-2',
        os.environ.get('S3_BUCKET_NAME', 'example-bucket') + '-3'
    ]
    s3_index = (int(time.time()) % len(s3_buckets))
    selected_bucket = s3_buckets[s3_index]
    
    # Add execution tag for S3 bucket
    add_execution_tag("s3_bucket", selected_bucket)
    
    logger.info(safe_json_serialize({
        "Data_Source": "Lambda_Handler",
        "Data_Target": "S3_Operations",
        "Data_Artifacts": {
            "bucket_name": selected_bucket,
            "aws_service": "S3",
            "round_robin_index": s3_index
        }
    }))
    
    try:
        # Check if bucket exists and create if needed
        bucket_ready = ensure_s3_bucket_exists(selected_bucket)
        
        if bucket_ready:
            # Existing S3 operations (client's existing code)
            s3_results = perform_s3_lifecycle_operations(selected_bucket)
            
            
            
            return {
                'bucket_used': selected_bucket,
                'objects_created': s3_results.get('objects_created', 0),
                'objects_deleted': s3_results.get('objects_deleted', 0)
            }
        else:
            add_execution_tag("s3_skipped", "true")
            return {
                'bucket_used': selected_bucket,
                'status': 'bucket_setup_failed'
            }
            
    except Exception as e:
        # Wrap S3 errors with Lumigo programmatic errors
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Error_Handling",
            "Data_Artifacts": {
                "error": str(e),
                "bucket_name": selected_bucket,
                "round_robin_index": s3_index
            }
        }))
        
        add_programmatic_error("S3_OPERATION_FAILED", str(e), {
            "bucket_name": selected_bucket,
            "error_type": type(e).__name__
        })
        
        return {
            'bucket_used': selected_bucket,
            'error': str(e)
        }

def ensure_s3_bucket_exists(bucket_name):
    """
    Check if S3 bucket exists and create it if needed.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "S3_Operations",
        "Data_Target": "Check_Bucket_Exists",
        "Data_Artifacts": {
            "bucket_name": bucket_name,
            "action": "check_bucket_exists",
            "aws_service": "S3"
        }
    }))
    
    try:
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Bucket_Exists",
                "Data_Artifacts": {
                    "bucket_name": bucket_name,
                    "action": "bucket_exists",
                    "aws_service": "S3"
                }
            }))
            

            return True
            
        except s3_client.exceptions.NoSuchBucket:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Bucket_Not_Found",
                "Data_Artifacts": {
                    "bucket_name": bucket_name,
                    "action": "bucket_not_found",
                    "aws_service": "S3"
                }
            }))
            
            return create_s3_bucket(bucket_name)
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Check_Bucket_Error",
                "Data_Artifacts": {
                    "bucket_name": bucket_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "check_bucket_error",
                    "aws_service": "S3"
                }
            }))
            
            add_execution_tag("s3_error", type(e).__name__)
            return False
            
    except Exception as e:
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Ensure_Bucket_Error",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "ensure_bucket_error",
                "aws_service": "S3"
            }
        }))
        
        add_execution_tag("s3_bucket_error", type(e).__name__)
        return False

def create_s3_bucket(bucket_name):
    """
    Create an S3 bucket for demonstration purposes.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "S3_Operations",
        "Data_Target": "Create_Bucket",
        "Data_Artifacts": {
            "bucket_name": bucket_name,
            "action": "create_bucket_start",
            "aws_service": "S3"
        }
    }))
    
    try:
        s3_client.create_bucket(Bucket=bucket_name)
        
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Create_Bucket_Success",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "action": "create_bucket_success",
                "aws_service": "S3"
            }
        }))
        
 
        return True
        
    except Exception as e:
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Create_Bucket_Error",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "create_bucket_error",
                "aws_service": "S3"
            }
        }))
        
        add_execution_tag("s3_bucket_error", type(e).__name__)
        return False

def perform_s3_lifecycle_operations(bucket_name):
    """
    Perform a complete S3 bucket lifecycle: upload objects, list them, then delete them.
    This demonstrates how to track S3 operations with execution tags.
    """
    import uuid
    from datetime import datetime
    
    # Generate unique identifiers for this operation
    operation_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    lifecycle_log = {
        'bucket_name': bucket_name,
        'operation_id': operation_id,
        'operations': [],
        'objects_created': 0,
        'objects_deleted': 0,
        'start_time': timestamp
    }
    
    try:
        # Step 1: Upload sample objects
        upload_results = upload_sample_objects(bucket_name, operation_id, timestamp)
        lifecycle_log['objects_created'] = upload_results.get('objects_created', 0)
        lifecycle_log['operations'].extend(upload_results.get('operations', []))
        
        # Step 2: List objects in the bucket
        list_results = list_bucket_objects(bucket_name, operation_id)
        lifecycle_log['operations'].extend(list_results.get('operations', []))
        
        # Step 3: Delete the objects we created
        delete_results = delete_bucket_objects(bucket_name, operation_id)
        lifecycle_log['objects_deleted'] = delete_results.get('objects_deleted', 0)
        lifecycle_log['operations'].extend(delete_results.get('operations', []))
        
        # Final summary
        lifecycle_log['end_time'] = datetime.utcnow().isoformat()
        lifecycle_log['total_success'] = True
        
        # Log the complete S3 lifecycle operation as JSON
        logger.info(f"S3 Lifecycle Operations Log: {json.dumps(lifecycle_log, indent=2)}")
        
        return {
            'bucket_name': bucket_name,
            'objects_created': lifecycle_log['objects_created'],
            'objects_deleted': lifecycle_log['objects_deleted'],
            'status': 'success'
        }
        
    except Exception as e:
        # Log error information
        error_log = {
            'bucket_name': bucket_name,
            'error': str(e),
            'error_type': type(e).__name__,
            'operations_completed': len(lifecycle_log['operations']),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"S3 Lifecycle Error Log: {json.dumps(error_log, indent=2)}")
        
        # Add execution tag for error
        add_execution_tag("s3_error", type(e).__name__)
        
        raise

def upload_sample_objects(bucket_name, operation_id, timestamp):
    """
    Upload sample objects to S3 bucket.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "S3_Operations",
        "Data_Target": "Upload_Sample_Objects",
        "Data_Artifacts": {
            "bucket_name": bucket_name,
            "operation_id": operation_id,
            "timestamp": timestamp,
            "action": "start_upload_operation",
            "objects_to_upload": 3
        }
    }))
    
    sample_objects = [
        {
            'key': f'sample-{operation_id}/data1.json',
            'content': json.dumps({
                'id': '1',
                'message': 'Sample data 1',
                'timestamp': timestamp,
                'operation_id': operation_id
            })
        },
        {
            'key': f'sample-{operation_id}/data2.json',
            'content': json.dumps({
                'id': '2',
                'message': 'Sample data 2',
                'timestamp': timestamp,
                'operation_id': operation_id
            })
        },
        {
            'key': f'sample-{operation_id}/metadata.txt',
            'content': f'Operation ID: {operation_id}\nTimestamp: {timestamp}\nBucket: {bucket_name}'
        }
    ]
    
    operations = []
    objects_created = 0
    
    for obj in sample_objects:
        try:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Upload_Object",
                "Data_Artifacts": {
                    "bucket_name": bucket_name,
                    "key": obj['key'],
                    "content_type": "application/json" if obj['key'].endswith('.json') else "text/plain",
                    "content_length": len(obj['content']),
                    "action": "upload_object",
                    "operation_id": operation_id
                }
            }))
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=obj['key'],
                Body=obj['content'],
                ContentType='application/json' if obj['key'].endswith('.json') else 'text/plain'
            )
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Upload_Object_Success",
                "Data_Artifacts": {
                    "bucket_name": bucket_name,
                    "key": obj['key'],
                    "action": "upload_object_success",
                    "operation_id": operation_id,
                    "timestamp": timestamp
                }
            }))
            
            objects_created += 1
            operations.append({
                'operation': 'UPLOAD_OBJECT',
                'status': 'success',
                'key': obj['key']
            })

            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Upload_Object_Error",
                "Data_Artifacts": {
                    "bucket_name": bucket_name,
                    "key": obj['key'],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "upload_object_error",
                    "operation_id": operation_id
                }
            }))
            
            operations.append({
                'operation': 'UPLOAD_OBJECT',
                'status': 'failed',
                'key': obj['key'],
                'error': str(e)
            })

    
    logger.info(safe_json_serialize({
        "Data_Source": "S3_Operations",
        "Data_Target": "Upload_Operation_Complete",
        "Data_Artifacts": {
            "bucket_name": bucket_name,
            "objects_created": objects_created,
            "total_objects": len(sample_objects),
            "failed_objects": len(sample_objects) - objects_created,
            "action": "upload_operation_complete",
            "operation_id": operation_id
        }
    }))
    
    return {
        'objects_created': objects_created,
        'operations': operations
    }

def list_bucket_objects(bucket_name, operation_id):
    """
    List objects in S3 bucket.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "S3_Operations",
        "Data_Target": "List_Bucket_Objects",
        "Data_Artifacts": {
            "bucket_name": bucket_name,
            "prefix": f'sample-{operation_id}/',
            "action": "list_objects_start",
            "operation_id": operation_id
        }
    }))
    
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f'sample-{operation_id}/')
        objects = response.get('Contents', [])
        
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "List_Objects_Success",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "prefix": f'sample-{operation_id}/',
                "object_count": len(objects),
                "objects": [obj['Key'] for obj in objects],
                "action": "list_objects_success",
                "operation_id": operation_id,
                "response_metadata": {
                    "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                    "http_status_code": response.get('ResponseMetadata', {}).get('HTTPStatusCode', 'unknown')
                }
            }
        }))
        
        operations = [{
            'operation': 'LIST_OBJECTS',
            'status': 'success',
            'object_count': len(objects)
        }]
        

        
        return {
            'operations': operations,
            'object_count': len(objects)
        }
        
    except Exception as e:
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "List_Objects_Error",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "prefix": f'sample-{operation_id}/',
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "list_objects_error",
                "operation_id": operation_id
            }
        }))
        
        operations = [{
            'operation': 'LIST_OBJECTS',
            'status': 'failed',
            'error': str(e)
        }]
        

        
        return {
            'operations': operations,
            'object_count': 0
        }

def delete_bucket_objects(bucket_name, operation_id):
    """
    Delete objects from S3 bucket.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "S3_Operations",
        "Data_Target": "Delete_Bucket_Objects",
        "Data_Artifacts": {
            "bucket_name": bucket_name,
            "prefix": f'sample-{operation_id}/',
            "action": "delete_objects_start",
            "operation_id": operation_id
        }
    }))
    
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f'sample-{operation_id}/')
        objects = response.get('Contents', [])
        
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Delete_Objects_List",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "prefix": f'sample-{operation_id}/',
                "objects_to_delete": len(objects),
                "object_keys": [obj['Key'] for obj in objects],
                "action": "delete_objects_list",
                "operation_id": operation_id
            }
        }))
        
        operations = []
        objects_deleted = 0
        
        for obj in objects:
            try:
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Delete_Object",
                    "Data_Artifacts": {
                        "bucket_name": bucket_name,
                        "key": obj['Key'],
                        "size": obj.get('Size', 0),
                        "last_modified": obj.get('LastModified', 'unknown'),
                        "action": "delete_object",
                        "operation_id": operation_id
                    }
                }))
                
                s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
                
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Delete_Object_Success",
                    "Data_Artifacts": {
                        "bucket_name": bucket_name,
                        "key": obj['Key'],
                        "action": "delete_object_success",
                        "operation_id": operation_id
                    }
                }))
                
                objects_deleted += 1
                operations.append({
                    'operation': 'DELETE_OBJECT',
                    'status': 'success',
                    'key': obj['Key']
                })

                
            except Exception as e:
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Delete_Object_Error",
                    "Data_Artifacts": {
                        "bucket_name": bucket_name,
                        "key": obj['Key'],
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "action": "delete_object_error",
                        "operation_id": operation_id
                    }
                }))
                
                operations.append({
                    'operation': 'DELETE_OBJECT',
                    'status': 'failed',
                    'key': obj['Key'],
                    'error': str(e)
                })

        
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Delete_Operation_Complete",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "objects_deleted": objects_deleted,
                "total_objects": len(objects),
                "failed_deletions": len(objects) - objects_deleted,
                "action": "delete_operation_complete",
                "operation_id": operation_id
            }
        }))
        
        return {
            'objects_deleted': objects_deleted,
            'operations': operations
        }
        
    except Exception as e:
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Delete_Objects_Error",
            "Data_Artifacts": {
                "bucket_name": bucket_name,
                "prefix": f'sample-{operation_id}/',
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "delete_objects_error",
                "operation_id": operation_id
            }
        }))
        
        operations = [{
            'operation': 'DELETE_OBJECTS',
            'status': 'failed',
            'error': str(e)
        }]
        
        add_execution_tag("s3_delete_error", type(e).__name__)
        
        return {
            'objects_deleted': 0,
            'operations': operations
        }

# =============================================================================
# COMPONENT 3: DATABASE OPERATIONS
# =============================================================================
def perform_database_operations():
    """
    Example: Wrap existing DynamoDB operations with Lumigo instrumentation.
    This is how clients would instrument their existing database calls.
    """
    # Round-robin through DynamoDB tables
    dynamodb_tables = [
        os.environ.get('DYNAMODB_TABLE_NAME', 'example-table'),
        os.environ.get('DYNAMODB_TABLE_NAME', 'example-table') + '-2',
        os.environ.get('DYNAMODB_TABLE_NAME', 'example-table') + '-3'
    ]
    db_index = (int(time.time()) % len(dynamodb_tables))
    selected_table = dynamodb_tables[db_index]
    
    # Add execution tag for database table
    add_execution_tag("dynamodb_table", selected_table)
    
    logger.info(safe_json_serialize({
        "Data_Source": "Lambda_Handler",
        "Data_Target": "Database_Operations",
        "Data_Artifacts": {
            "table_name": selected_table,
            "aws_service": "DynamoDB",
            "round_robin_index": db_index
        }
    }))
    
    try:
        # Check if table exists and create if needed
        table_ready = ensure_dynamodb_table_exists(selected_table)
        
        if table_ready:
            # Existing database operations (client's existing code)
            crud_results = perform_dynamodb_crud_operations(selected_table)
            
            return {
                'table_used': selected_table,
                'operations_count': crud_results.get('operations_count', 0),
                'item_id': crud_results.get('item_id', 'unknown')
            }
        else:
            return {
                'table_used': selected_table,
                'status': 'table_setup_failed'
            }
            
    except Exception as e:
        # Wrap database errors with Lumigo programmatic errors
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Error_Handling",
            "Data_Artifacts": {
                "error": str(e),
                "table_name": selected_table,
                "round_robin_index": db_index
            }
        }))
        
        add_programmatic_error("DATABASE_OPERATION_FAILED", str(e), {
            "table_name": selected_table,
            "error_type": type(e).__name__
        })
        
        return {
            'table_used': selected_table,
            'error': str(e)
        }

def ensure_dynamodb_table_exists(table_name):
    """
    Check if DynamoDB table exists and create it if needed.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "Database_Operations",
        "Data_Target": "Check_Table_Exists",
        "Data_Artifacts": {
            "table_name": table_name,
            "action": "check_table_exists",
            "aws_service": "DynamoDB"
        }
    }))
    
    try:
        try:
            response = dynamodb_client.describe_table(TableName=table_name)
            table_status = response['Table']['TableStatus']
            
            logger.info(safe_json_serialize({
                "Data_Source": "Database_Operations",
                "Data_Target": "Table_Exists",
                "Data_Artifacts": {
                    "table_name": table_name,
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
                        "table_name": table_name,
                        "table_status": table_status,
                        "action": "wait_for_table_active",
                        "aws_service": "DynamoDB"
                    }
                }))
                
                # Wait for table to become active
                waiter = dynamodb_client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "Database_Operations",
                    "Data_Target": "Table_Now_Active",
                    "Data_Artifacts": {
                        "table_name": table_name,
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
                        "table_name": table_name,
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
                    "table_name": table_name,
                    "action": "table_not_found",
                    "aws_service": "DynamoDB"
                }
            }))
            
            return create_dynamodb_table(table_name)
            
    except Exception as e:
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Check_Table_Error",
            "Data_Artifacts": {
                "table_name": table_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "check_table_error",
                "aws_service": "DynamoDB"
            }
        }))
        
        return False

def perform_dynamodb_crud_operations(table_name):
    """
    Perform a complete CRUD round trip on DynamoDB.
    This demonstrates how to track database operations with execution tags.
    """
    import uuid
    from datetime import datetime
    
    # Generate a unique item ID for this operation
    item_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    logger.info(safe_json_serialize({
        "Data_Source": "Database_Operations",
        "Data_Target": "CRUD_Operations_Start",
        "Data_Artifacts": {
            "table_name": table_name,
            "item_id": item_id,
            "timestamp": timestamp,
            "action": "start_crud_operations",
            "operations_planned": ["CREATE", "READ", "UPDATE", "DELETE"]
        }
    }))
    
    crud_log = {
        'table_name': table_name,
        'item_id': item_id,
        'operations': [],
        'operations_count': 0,
        'start_time': timestamp
    }
    
    try:
        # CREATE operation
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Create_Item",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "create_item",
                "item_data": {
                    "id": item_id,
                    "timestamp": timestamp,
                    "data": "Sample data for CRUD demonstration",
                    "status": "active",
                    "metadata": {"created_by": "lambda-function", "version": "1.0"}
                }
            }
        }))
        
        create_response = dynamodb_client.put_item(
            TableName=table_name,
            Item={
                'id': {'S': item_id},
                'timestamp': {'S': timestamp},
                'data': {'S': 'Sample data for CRUD demonstration'},
                'status': {'S': 'active'},
                'metadata': {'S': json.dumps({'created_by': 'lambda-function', 'version': '1.0'})}
            }
        )
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Create_Item_Success",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "create_item_success",
                "response_metadata": {
                    "request_id": create_response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                    "consumed_capacity": create_response.get('ConsumedCapacity', {})
                }
            }
        }))
        
        create_log = {
            'operation': 'CREATE',
            'status': 'success',
            'item_id': item_id,
            'response': {
                'consumed_capacity': create_response.get('ConsumedCapacity', {}),
                'request_id': create_response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            }
        }
        crud_log['operations'].append(create_log)
        crud_log['operations_count'] += 1
        

        
        # READ operation
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Read_Item",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "read_item",
                "key": {"id": item_id}
            }
        }))
        
        read_response = dynamodb_client.get_item(
            TableName=table_name,
            Key={'id': {'S': item_id}}
        )
        
        item_found = 'Item' in read_response
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Read_Item_Result",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "read_item_result",
                "item_found": item_found,
                "item_data": read_response.get('Item', {}),
                "response_metadata": {
                    "request_id": read_response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                    "consumed_capacity": read_response.get('ConsumedCapacity', {})
                }
            }
        }))
        
        read_log = {
            'operation': 'READ',
            'status': 'success' if item_found else 'not_found',
            'item_id': item_id,
            'item_found': item_found,
            'response': {
                'consumed_capacity': read_response.get('ConsumedCapacity', {}),
                'request_id': read_response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            }
        }
        crud_log['operations'].append(read_log)
        crud_log['operations_count'] += 1
        

        
        # UPDATE operation
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Update_Item",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "update_item",
                "update_expression": "SET #status = :status, #updated_at = :updated_at",
                "expression_attribute_names": {
                    "#status": "status",
                    "#updated_at": "updated_at"
                },
                "expression_attribute_values": {
                    ":status": "updated",
                    ":updated_at": datetime.utcnow().isoformat()
                }
            }
        }))
        
        update_response = dynamodb_client.update_item(
            TableName=table_name,
            Key={'id': {'S': item_id}},
            UpdateExpression='SET #status = :status, #updated_at = :updated_at',
            ExpressionAttributeNames={
                '#status': 'status',
                '#updated_at': 'updated_at'
            },
            ExpressionAttributeValues={
                ':status': {'S': 'updated'},
                ':updated_at': {'S': datetime.utcnow().isoformat()}
            },
            ReturnValues='ALL_NEW'
        )
        
        updated_attributes = list(update_response.get('Attributes', {}).keys())
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Update_Item_Success",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "update_item_success",
                "updated_attributes": updated_attributes,
                "new_item_data": update_response.get('Attributes', {}),
                "response_metadata": {
                    "request_id": update_response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                    "consumed_capacity": update_response.get('ConsumedCapacity', {})
                }
            }
        }))
        
        update_log = {
            'operation': 'UPDATE',
            'status': 'success',
            'item_id': item_id,
            'updated_attributes': updated_attributes,
            'response': {
                'consumed_capacity': update_response.get('ConsumedCapacity', {}),
                'request_id': update_response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            }
        }
        crud_log['operations'].append(update_log)
        crud_log['operations_count'] += 1
        

        
        # DELETE operation - SKIPPED (keeping data in table)
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Delete_Item_Skipped",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "delete_item_skipped",
                "reason": "Data preservation requested - keeping items in table",
                "aws_service": "DynamoDB"
            }
        }))
        
        delete_log = {
            'operation': 'DELETE',
            'status': 'skipped',
            'item_id': item_id,
            'reason': 'Data preservation requested - keeping items in table'
        }
        crud_log['operations'].append(delete_log)
        crud_log['operations_count'] += 1
        
        # Final summary
        crud_log['end_time'] = datetime.utcnow().isoformat()
        crud_log['total_success'] = True
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "CRUD_Operations_Complete",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "crud_operations_complete",
                "operations_count": crud_log['operations_count'],
                "operations": crud_log['operations'],
                "total_success": True,
                "start_time": crud_log['start_time'],
                "end_time": crud_log['end_time']
            }
        }))
        
        return {
            'item_id': item_id,
            'operations_count': crud_log['operations_count'],
            'status': 'success',
            'table_name': table_name
        }
        
    except Exception as e:
        # Log error information
        error_log = {
            'table_name': table_name,
            'error': str(e),
            'error_type': type(e).__name__,
            'operations_completed': crud_log['operations_count'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "CRUD_Operations_Error",
            "Data_Artifacts": {
                "table_name": table_name,
                "item_id": item_id,
                "action": "crud_operations_error",
                "error": str(e),
                "error_type": type(e).__name__,
                "operations_completed": crud_log['operations_count'],
                "timestamp": datetime.utcnow().isoformat()
            }
        }))
        
        raise

def create_dynamodb_table(table_name):
    """
    Create a DynamoDB table for demonstration purposes.
    """
    logger.info(safe_json_serialize({
        "Data_Source": "Database_Operations",
        "Data_Target": "Create_Table",
        "Data_Artifacts": {
            "table_name": table_name,
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
            TableName=table_name,
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
                "table_name": table_name,
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
                "table_name": table_name,
                "action": "wait_for_table_active",
                "aws_service": "DynamoDB"
            }
        }))
        
        waiter = dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
        
        logger.info(safe_json_serialize({
            "Data_Source": "Database_Operations",
            "Data_Target": "Table_Active",
            "Data_Artifacts": {
                "table_name": table_name,
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
                    "table_name": table_name,
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
                    "table_name": table_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "create_table_error",
                    "aws_service": "DynamoDB"
                }
            }))
            

            return False

def delete_dynamodb_table(table_name):
    """
    Delete a DynamoDB table for cleanup.
    Can be triggered via event instruction.
    """
    try:
        logger.info(f"Deleting DynamoDB table: {table_name}")
        
        response = dynamodb_client.delete_table(TableName=table_name)
        
        logger.info(f"Table {table_name} deleted successfully")
        add_execution_tag("dynamodb_table_deleted", "true")
        
        return True
        
    except Exception as e:
        logger.info(f"Failed to delete table {table_name}: {str(e)}")
        add_execution_tag("dynamodb_error", type(e).__name__)
        return False

# =============================================================================
# LUMIGO INSTRUMENTATION HELPERS
# =============================================================================
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

