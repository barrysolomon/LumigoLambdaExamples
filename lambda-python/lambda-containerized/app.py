import json
from lumigo_tracer import lumigo_tracer

@lumigo_tracer()
def lambda_handler(event, context):
  return {
    'statusCode': 200,
    'body': json.dumps(event)
  }