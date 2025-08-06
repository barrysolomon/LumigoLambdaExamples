import requests
import time
import logging
from datetime import datetime

logger = logging.getLogger()

class APIDAL:
    def __init__(self):
        self.session = requests.Session()
    
    def fetch_data(self, endpoint, params=None):
        """Fetch data from external API."""
        try:
            start_time = time.time()
            response = self.session.get(endpoint, params=params)
            response_time = time.time() - start_time
            
            logger.info(f"API Request - {endpoint} completed in {response_time:.3f}s")
            return {
                'status_code': response.status_code,
                'data': response.json(),
                'response_time': response_time,
                'endpoint': endpoint
            }
        except Exception as e:
            logger.error(f"API Request - Error: {str(e)}")
            raise 