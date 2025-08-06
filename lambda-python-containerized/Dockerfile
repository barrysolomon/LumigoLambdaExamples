FROM public.ecr.aws/lambda/python:3.11-x86_64

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install -r requirements.txt

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set default environment variables for turnkey deployment
ENV LUMIGO_TRACER_TOKEN=""
ENV OTEL_SERVICE_NAME="lambda-python-lumigo-example"
ENV LUMIGO_ENABLE_LOGS="true"
ENV DYNAMODB_TABLE_NAME="example-table"
ENV S3_BUCKET_NAME="example-bucket"

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ] 