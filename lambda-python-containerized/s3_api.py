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

# Initialize S3 client
s3_client = boto3.client('s3')

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

class S3DAL:
    """
    Data Access Layer for S3 operations with built-in Lumigo instrumentation.
    This class encapsulates all S3 operations with proper logging and execution tags.
    """
    
    def __init__(self, bucket_name=None):
        """
        Initialize the DAL with a specific bucket name or use round-robin selection.
        """
        if bucket_name:
            self.bucket_name = bucket_name
            self.round_robin_index = None
        else:
            # Round-robin through S3 buckets
            s3_buckets = [
                os.environ.get('S3_BUCKET_NAME', 'example-bucket'),
                os.environ.get('S3_BUCKET_NAME', 'example-bucket') + '-2',
                os.environ.get('S3_BUCKET_NAME', 'example-bucket') + '-3'
            ]
            self.round_robin_index = (int(time.time()) % len(s3_buckets))
            self.bucket_name = s3_buckets[self.round_robin_index]
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "S3_Operations",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
                "aws_service": "S3",
                "round_robin_index": self.round_robin_index
            }
        }))
    
    def ensure_bucket_exists(self):
        """
        Check if S3 bucket exists and create it if needed.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Check_Bucket_Exists",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
                "action": "check_bucket_exists",
                "aws_service": "S3"
            }
        }))
        
        try:
            try:
                s3_client.head_bucket(Bucket=self.bucket_name)
                
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Bucket_Exists",
                    "Data_Artifacts": {
                        "bucket_name": self.bucket_name,
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
                        "bucket_name": self.bucket_name,
                        "action": "bucket_not_found",
                        "aws_service": "S3"
                    }
                }))
                
                return self.create_bucket()
                
            except Exception as e:
                logger.info(safe_json_serialize({
                    "Data_Source": "S3_Operations",
                    "Data_Target": "Check_Bucket_Error",
                    "Data_Artifacts": {
                        "bucket_name": self.bucket_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "action": "check_bucket_error",
                        "aws_service": "S3"
                    }
                }))
                
                return False
                
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Ensure_Bucket_Error",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "ensure_bucket_error",
                    "aws_service": "S3"
                }
            }))
            
            return False
    
    def create_bucket(self):
        """
        Create an S3 bucket for demonstration purposes.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Create_Bucket",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
                "action": "create_bucket_start",
                "aws_service": "S3"
            }
        }))
        
        try:
            s3_client.create_bucket(Bucket=self.bucket_name)
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Create_Bucket_Success",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
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
                    "bucket_name": self.bucket_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "create_bucket_error",
                    "aws_service": "S3"
                }
            }))
            
            return False
    
    def upload_object(self, key, content, content_type='application/json'):
        """
        Upload an object to S3 bucket.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Upload_Object",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
                "key": key,
                "content_type": content_type,
                "content_length": len(content),
                "action": "upload_object",
                "aws_service": "S3"
            }
        }))
        
        try:
            s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type
            )
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Upload_Object_Success",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "key": key,
                    "action": "upload_object_success",
                    "aws_service": "S3"
                }
            }))
            
            return {
                'status': 'success',
                'key': key,
                'bucket': self.bucket_name
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Upload_Object_Error",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "key": key,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "upload_object_error",
                    "aws_service": "S3"
                }
            }))
            
            raise
    
    def list_objects(self, prefix=None):
        """
        List objects in S3 bucket.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "List_Objects",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
                "prefix": prefix,
                "action": "list_objects_start",
                "aws_service": "S3"
            }
        }))
        
        try:
            response = s3_client.list_objects_v2(
                Bucket=self.bucket_name, 
                Prefix=prefix
            )
            objects = response.get('Contents', [])
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "List_Objects_Success",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "prefix": prefix,
                    "object_count": len(objects),
                    "objects": [obj['Key'] for obj in objects],
                    "action": "list_objects_success",
                    "aws_service": "S3",
                    "response_metadata": {
                        "request_id": response.get('ResponseMetadata', {}).get('RequestId', 'unknown'),
                        "http_status_code": response.get('ResponseMetadata', {}).get('HTTPStatusCode', 'unknown')
                    }
                }
            }))
            
            return {
                'status': 'success',
                'object_count': len(objects),
                'objects': [obj['Key'] for obj in objects],
                'bucket': self.bucket_name
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "List_Objects_Error",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "prefix": prefix,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "list_objects_error",
                    "aws_service": "S3"
                }
            }))
            
            raise
    
    def delete_object(self, key):
        """
        Delete an object from S3 bucket.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Delete_Object",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
                "key": key,
                "action": "delete_object",
                "aws_service": "S3"
            }
        }))
        
        try:
            s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Delete_Object_Success",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "key": key,
                    "action": "delete_object_success",
                    "aws_service": "S3"
                }
            }))
            
            return {
                'status': 'success',
                'key': key,
                'bucket': self.bucket_name
            }
            
        except Exception as e:
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Delete_Object_Error",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "key": key,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "delete_object_error",
                    "aws_service": "S3"
                }
            }))
            
            raise
    
    def upload_sample_objects(self, operation_id, timestamp):
        """
        Upload sample objects to S3 bucket.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "S3_Operations",
            "Data_Target": "Upload_Sample_Objects",
            "Data_Artifacts": {
                "bucket_name": self.bucket_name,
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
                'content': f'Operation ID: {operation_id}\nTimestamp: {timestamp}\nBucket: {self.bucket_name}'
            }
        ]
        
        operations = []
        objects_created = 0
        
        for obj in sample_objects:
            try:
                result = self.upload_object(
                    obj['key'], 
                    obj['content'],
                    'application/json' if obj['key'].endswith('.json') else 'text/plain'
                )
                
                objects_created += 1
                operations.append({
                    'operation': 'UPLOAD_OBJECT',
                    'status': 'success',
                    'key': obj['key']
                })
                
            except Exception as e:
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
                "bucket_name": self.bucket_name,
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
    
    def list_bucket_objects(self, operation_id):
        """
        List objects in S3 bucket.
        """
        try:
            result = self.list_objects(f'sample-{operation_id}/')
            
            operations = [{
                'operation': 'LIST_OBJECTS',
                'status': 'success',
                'object_count': result.get('object_count', 0)
            }]
            
            return {
                'operations': operations,
                'object_count': result.get('object_count', 0)
            }
            
        except Exception as e:
            operations = [{
                'operation': 'LIST_OBJECTS',
                'status': 'failed',
                'error': str(e)
            }]
            
            return {
                'operations': operations,
                'object_count': 0
            }
    
    def delete_bucket_objects(self, operation_id):
        """
        Delete objects from S3 bucket.
        """
        try:
            # First list objects to delete
            list_result = self.list_objects(f'sample-{operation_id}/')
            objects_to_delete = list_result.get('objects', [])
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Delete_Objects_List",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "prefix": f'sample-{operation_id}/',
                    "objects_to_delete": len(objects_to_delete),
                    "object_keys": objects_to_delete,
                    "action": "delete_objects_list",
                    "operation_id": operation_id
                }
            }))
            
            operations = []
            objects_deleted = 0
            
            for obj_key in objects_to_delete:
                try:
                    result = self.delete_object(obj_key)
                    
                    objects_deleted += 1
                    operations.append({
                        'operation': 'DELETE_OBJECT',
                        'status': 'success',
                        'key': obj_key
                    })
                    
                except Exception as e:
                    operations.append({
                        'operation': 'DELETE_OBJECT',
                        'status': 'failed',
                        'key': obj_key,
                        'error': str(e)
                    })
            
            logger.info(safe_json_serialize({
                "Data_Source": "S3_Operations",
                "Data_Target": "Delete_Operation_Complete",
                "Data_Artifacts": {
                    "bucket_name": self.bucket_name,
                    "objects_deleted": objects_deleted,
                    "total_objects": len(objects_to_delete),
                    "failed_deletions": len(objects_to_delete) - objects_deleted,
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
                    "bucket_name": self.bucket_name,
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
            
            return {
                'objects_deleted': 0,
                'operations': operations
            } 