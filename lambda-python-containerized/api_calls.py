import json
import os
import time
import logging
import requests
from datetime import datetime
from opentelemetry import trace

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

class APIDAL:
    """
    Data Access Layer for API operations with built-in Lumigo instrumentation.
    This class encapsulates all HTTP API operations with proper logging and execution tags.
    """
    
    def __init__(self, endpoint=None):
        """
        Initialize the DAL with a specific endpoint or use round-robin selection.
        """
        if endpoint:
            self.endpoint = endpoint
            self.round_robin_index = None
        else:
            # Round-robin through API endpoints
            api_endpoints = [
                "https://jsonplaceholder.typicode.com/posts/1",
                "https://jsonplaceholder.typicode.com/posts/2", 
                "https://jsonplaceholder.typicode.com/posts/3"
            ]
            self.round_robin_index = (int(time.time()) % len(api_endpoints))
            self.endpoint = api_endpoints[self.round_robin_index]
        
        logger.info(safe_json_serialize({
            "Data_Source": "Lambda_Handler",
            "Data_Target": "API_Operations",
            "Data_Artifacts": {
                "endpoint": self.endpoint,
                "method": "GET",
                "service": "JSONPlaceholder_API",
                "round_robin_index": self.round_robin_index
            }
        }))
    
    def fetch_data(self, timeout=10):
        """
        Fetch data from the configured API endpoint.
        """
        logger.info(safe_json_serialize({
            "Data_Source": "External_API",
            "Data_Target": "JSONPlaceholder",
            "Data_Artifacts": {
                "endpoint": self.endpoint,
                "method": "GET",
                "timeout": timeout,
                "action": "fetch_api_data_start",
                "service": "JSONPlaceholder_API"
            }
        }))
        
        try:
            # Make the HTTP request
            response = requests.get(self.endpoint, timeout=timeout)
            
            logger.info(safe_json_serialize({
                "Data_Source": "External_API",
                "Data_Target": "API_Response_Received",
                "Data_Artifacts": {
                    "endpoint": self.endpoint,
                    "method": "GET",
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None,
                    "content_length": len(response.content),
                    "headers": dict(response.headers),
                    "action": "api_response_received",
                    "service": "JSONPlaceholder_API"
                }
            }))
            
            # Raise an exception for bad status codes
            response.raise_for_status()
            
            # Parse the JSON response
            post_data = response.json()
            
            logger.info(safe_json_serialize({
                "Data_Source": "External_API",
                "Data_Target": "API_Data_Parsed",
                "Data_Artifacts": {
                    "endpoint": self.endpoint,
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
                    "endpoint": self.endpoint,
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
                'endpoint_used': self.endpoint,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
            }
            
        except requests.RequestException as e:
            logger.info(safe_json_serialize({
                "Data_Source": "External_API",
                "Data_Target": "API_Request_Error",
                "Data_Artifacts": {
                    "endpoint": self.endpoint,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "api_request_error",
                    "service": "JSONPlaceholder_API"
                }
            }))
            
            raise 