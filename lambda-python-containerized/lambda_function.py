import json
import os
import requests
import boto3
from lumigo_opentelemetry import lumigo_wrapped
from opentelemetry import trace

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb_client = boto3.client('dynamodb')

@lumigo_wrapped
def lambda_handler(event, context):
    """
    Example Lambda function with Lumigo OpenTelemetry instrumentation.
    This function demonstrates various operations that will be traced.
    """
    try:
        # Log the incoming event
        print(f"Received event: {json.dumps(event)}")
        
        # Add execution tags from event data
        add_execution_tags_from_event(event)
        
        # Example 1: Make an HTTP request (will be traced)
        print("Making HTTP request to external API...")
        response = requests.get('https://jsonplaceholder.typicode.com/posts/1', timeout=10)
        response.raise_for_status()
        post_data = response.json()
        print(f"Retrieved post: {post_data['title']}")
        
        # Add execution tag for successful API call
        add_execution_tag("api_call_status", "success")
        add_execution_tag("post_id", str(post_data.get('id', 'unknown')))
        
        # Example 2: S3 operation (will be traced)
        print("Performing S3 operation...")
        bucket_name = os.environ.get('S3_BUCKET_NAME', 'example-bucket')
        try:
            # List buckets (this will be traced)
            buckets = s3_client.list_buckets()
            bucket_count = len(buckets['Buckets'])
            print(f"Found {bucket_count} buckets")
            
            # Add execution tag for S3 operation
            add_execution_tag("s3_bucket_count", str(bucket_count))
            add_execution_tag("s3_operation", "list_buckets")
            
        except Exception as e:
            print(f"S3 operation failed: {str(e)}")
            add_execution_tag("s3_operation_status", "failed")
            add_execution_tag("s3_error_type", type(e).__name__)
            raise
        
        # Example 3: DynamoDB CRUD operations (will be traced)
        print("Performing DynamoDB CRUD operations...")
        table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'example-table')
        
        # Check for delete table instruction in event
        if event.get('action') == 'delete_table':
            print("Delete table instruction received")
            add_execution_tag("dynamodb_action", "delete_table")
            delete_success = delete_dynamodb_table(table_name)
            if delete_success:
                print("Table deletion completed successfully")
            else:
                print("Table deletion failed")
            return
        
        # Check if table exists and create if needed
        table_ready = ensure_dynamodb_table_exists(table_name)
        
        if table_ready:
            try:
                # CRUD Operations
                crud_results = perform_dynamodb_crud_operations(table_name)
                
                # Add execution tags for DynamoDB operations
                add_execution_tag("dynamodb_table", table_name)
                add_execution_tag("dynamodb_operations", "create,read,update,delete")
                add_execution_tag("dynamodb_status", "success")
                add_execution_tag("dynamodb_item_id", crud_results.get('item_id', 'unknown'))
                add_execution_tag("dynamodb_operations_count", str(crud_results.get('operations_count', 0)))
                
            except Exception as e:
                print(f"DynamoDB CRUD operations failed: {str(e)}")
                add_execution_tag("dynamodb_status", "failed")
                add_execution_tag("dynamodb_error", type(e).__name__)
                # Don't raise the exception - just log it and continue
                print(f"Continuing execution despite DynamoDB error: {str(e)}")
        else:
            print("Skipping DynamoDB operations due to table setup failure")
            add_execution_tag("dynamodb_skipped", "true")
        
        # Example 4: Custom business logic
        print("Processing business logic...")
        result = process_business_logic(event)
        
        # Add execution tag for business logic
        add_execution_tag("business_logic_result", result)
        add_execution_tag("processing_status", "completed")
        
        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Lambda function executed successfully',
                'post_title': post_data['title'],
                'result': result,
                'request_id': context.aws_request_id
            })
        }
        
    except requests.RequestException as e:
        # Programmatic error for HTTP request failures
        error_message = f"HTTP request failed: {str(e)}"
        print(error_message)
        add_execution_tag("error_category", "http_request")
        add_execution_tag("error_type", type(e).__name__)
        add_execution_tag("processing_status", "failed")
        
        # Create programmatic error
        create_programmatic_error("HTTP_REQUEST_FAILED", error_message, {
            "url": "https://jsonplaceholder.typicode.com/posts/1",
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
        # Programmatic error for general failures
        error_message = f"Lambda execution failed: {str(e)}"
        print(error_message)
        add_execution_tag("error_category", "general")
        add_execution_tag("error_type", type(e).__name__)
        add_execution_tag("processing_status", "failed")
        
        # Create programmatic error
        create_programmatic_error("LAMBDA_EXECUTION_FAILED", error_message, {
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

def add_execution_tag(key, value):
    """
    Add an execution tag to the current span.
    Execution tags help identify, search for, and filter invocations in Lumigo.
    """
    try:
        # Use the correct OpenTelemetry API
        from opentelemetry import trace as otel_trace
        active_span = otel_trace.get_current_span()
        if active_span:
            # Add the lumigo.execution_tags prefix as required by Lumigo
            active_span.set_attribute(f"lumigo.execution_tags.{key}", str(value))
            print(f"Added execution tag: {key} = {value}")
    except Exception as e:
        print(f"Failed to add execution tag {key}: {str(e)}")

def add_execution_tags_from_event(event):
    """
    Add execution tags from the Lambda event data.
    This demonstrates how to extract meaningful tags from the incoming event.
    """
    try:
        # Add tags from event data
        if 'data' in event:
            add_execution_tag("has_data", "true")
            add_execution_tag("data_length", str(len(event['data'])))
        else:
            add_execution_tag("has_data", "false")
        
        if 'test' in event:
            add_execution_tag("is_test", str(event['test']))
        
        if 'source' in event:
            add_execution_tag("event_source", event['source'])
        
        if 'timestamp' in event:
            add_execution_tag("event_timestamp", event['timestamp'])
            
    except Exception as e:
        print(f"Failed to add execution tags from event: {str(e)}")

def create_programmatic_error(error_code, message, additional_data=None):
    """
    Create a programmatic error that will be captured by Lumigo.
    This allows for custom error categorization and better debugging.
    """
    try:
        # Use the correct OpenTelemetry API
        from opentelemetry import trace as otel_trace
        active_span = otel_trace.get_current_span()
        if active_span:
            # Set error attributes on the span
            active_span.set_attribute("error", True)
            active_span.set_attribute("error.message", message)
            active_span.set_attribute("error.type", error_code)
            
            # Add additional error data if provided
            if additional_data:
                for key, value in additional_data.items():
                    active_span.set_attribute(f"error.{key}", str(value))
            
            print(f"Created programmatic error: {error_code} - {message}")
    except Exception as e:
        print(f"Failed to create programmatic error: {str(e)}")

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
    
    # Create item data
    item_data = {
        'id': item_id,
        'timestamp': timestamp,
        'data': 'Sample data for CRUD demonstration',
        'status': 'active',
        'metadata': {
            'created_by': 'lambda-function',
            'version': '1.0'
        }
    }
    
    crud_log = {
        'table_name': table_name,
        'item_id': item_id,
        'operations': [],
        'operations_count': 0,
        'start_time': timestamp
    }
    
    try:
        # CREATE operation
        print(f"Creating item {item_id} in table {table_name}...")
        create_response = dynamodb_client.put_item(
            TableName=table_name,
            Item={
                'id': {'S': item_id},
                'timestamp': {'S': timestamp},
                'data': {'S': item_data['data']},
                'status': {'S': item_data['status']},
                'metadata': {'S': json.dumps(item_data['metadata'])}
            }
        )
        
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
        
        # Add execution tag for CREATE
        add_execution_tag("dynamodb_create", "success")
        add_execution_tag("dynamodb_item_id", item_id[:20])  # Truncate to stay under 75 chars
        
        # READ operation
        print(f"Reading item {item_id} from table {table_name}...")
        read_response = dynamodb_client.get_item(
            TableName=table_name,
            Key={'id': {'S': item_id}}
        )
        
        read_log = {
            'operation': 'READ',
            'status': 'success' if 'Item' in read_response else 'not_found',
            'item_id': item_id,
            'item_found': 'Item' in read_response,
            'response': {
                'consumed_capacity': read_response.get('ConsumedCapacity', {}),
                'request_id': read_response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            }
        }
        crud_log['operations'].append(read_log)
        crud_log['operations_count'] += 1
        
        # Add execution tag for READ
        add_execution_tag("dynamodb_read", "success")
        add_execution_tag("dynamodb_item_found", "true" if 'Item' in read_response else "false")
        
        # UPDATE operation
        print(f"Updating item {item_id} in table {table_name}...")
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
        
        update_log = {
            'operation': 'UPDATE',
            'status': 'success',
            'item_id': item_id,
            'updated_attributes': list(update_response.get('Attributes', {}).keys()),
            'response': {
                'consumed_capacity': update_response.get('ConsumedCapacity', {}),
                'request_id': update_response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            }
        }
        crud_log['operations'].append(update_log)
        crud_log['operations_count'] += 1
        
        # Add execution tag for UPDATE
        add_execution_tag("dynamodb_update", "success")
        add_execution_tag("dynamodb_updated_attrs", str(len(update_log['updated_attributes'])))
        
        # DELETE operation
        print(f"Deleting item {item_id} from table {table_name}...")
        delete_response = dynamodb_client.delete_item(
            TableName=table_name,
            Key={'id': {'S': item_id}},
            ReturnValues='ALL_OLD'
        )
        
        delete_log = {
            'operation': 'DELETE',
            'status': 'success',
            'item_id': item_id,
            'deleted_item': 'Item' in delete_response,
            'response': {
                'consumed_capacity': delete_response.get('ConsumedCapacity', {}),
                'request_id': delete_response.get('ResponseMetadata', {}).get('RequestId', 'unknown')
            }
        }
        crud_log['operations'].append(delete_log)
        crud_log['operations_count'] += 1
        
        # Add execution tag for DELETE
        add_execution_tag("dynamodb_delete", "success")
        add_execution_tag("dynamodb_deleted", "true" if delete_log['deleted_item'] else "false")
        
        # Final summary
        crud_log['end_time'] = datetime.utcnow().isoformat()
        crud_log['total_success'] = True
        
        # Log the complete CRUD operation as JSON
        print(f"DynamoDB CRUD Operations Log: {json.dumps(crud_log, indent=2)}")
        
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
        
        print(f"DynamoDB CRUD Error Log: {json.dumps(error_log, indent=2)}")
        
        # Add execution tags for error
        add_execution_tag("dynamodb_crud_error", type(e).__name__)
        add_execution_tag("dynamodb_ops_completed", str(crud_log['operations_count']))
        
        raise

def ensure_dynamodb_table_exists(table_name):
    """
    Check if DynamoDB table exists and create it if needed.
    Returns True if table is ready for use, False otherwise.
    """
    try:
        # First, try to describe the table to see if it exists
        try:
            response = dynamodb_client.describe_table(TableName=table_name)
            table_status = response['Table']['TableStatus']
            
            if table_status == 'ACTIVE':
                print(f"Table {table_name} already exists and is active")
                add_execution_tag("dynamodb_table_exists", "true")
                add_execution_tag("dynamodb_table_status", "active")
                return True
            elif table_status in ['CREATING', 'UPDATING']:
                print(f"Table {table_name} is being created/updated, waiting...")
                add_execution_tag("dynamodb_table_status", table_status.lower())
                
                # Wait for table to become active
                waiter = dynamodb_client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                print(f"Table {table_name} is now active")
                add_execution_tag("dynamodb_table_status", "active")
                return True
            else:
                print(f"Table {table_name} exists but status is {table_status}")
                add_execution_tag("dynamodb_table_status", table_status.lower())
                return False
                
        except dynamodb_client.exceptions.ResourceNotFoundException:
            # Table doesn't exist, create it
            print(f"Table {table_name} doesn't exist, creating...")
            return create_dynamodb_table(table_name)
            
    except Exception as e:
        print(f"Error checking/creating table {table_name}: {str(e)}")
        add_execution_tag("dynamodb_table_error", type(e).__name__)
        return False

def create_dynamodb_table(table_name):
    """
    Create a DynamoDB table for demonstration purposes.
    """
    try:
        print(f"Creating DynamoDB table: {table_name}")
        
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
        
        print(f"Table {table_name} created successfully")
        add_execution_tag("dynamodb_table_created", "true")
        
        # Wait for table to be active
        waiter = dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
        print(f"Table {table_name} is now active")
        
        return True
        
    except Exception as e:
        if 'Table already exists' in str(e):
            print(f"Table {table_name} already exists")
            add_execution_tag("dynamodb_table_exists", "true")
            return True
        else:
            print(f"Failed to create table {table_name}: {str(e)}")
            add_execution_tag("dynamodb_table_created", "false")
            add_execution_tag("dynamodb_table_error", type(e).__name__)
            return False


def delete_dynamodb_table(table_name):
    """
    Delete a DynamoDB table for cleanup.
    Can be triggered via event instruction.
    """
    try:
        print(f"Deleting DynamoDB table: {table_name}")
        
        response = dynamodb_client.delete_table(TableName=table_name)
        
        print(f"Table {table_name} deleted successfully")
        add_execution_tag("dynamodb_table_deleted", "true")
        
        return True
        
    except Exception as e:
        print(f"Failed to delete table {table_name}: {str(e)}")
        add_execution_tag("dynamodb_table_deleted", "false")
        add_execution_tag("dynamodb_delete_error", type(e).__name__)
        return False

def process_business_logic(event):
    """
    Example business logic function that will be traced as part of the main span.
    """
    # Simulate some processing
    if 'data' in event:
        processed_data = event['data'].upper()
        return f"Processed: {processed_data}"
    else:
        return "No data to process" 