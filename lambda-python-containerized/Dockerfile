FROM public.ecr.aws/lambda/python:3.11-x86_64

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY lambda_function.py /var/task/
COPY dynamodb_api.py /var/task/
COPY s3_api.py /var/task/
COPY api_calls.py /var/task/
COPY postgresql_api.py /var/task/

# Set default environment variables for turnkey deployment
ENV LUMIGO_TRACER_TOKEN=""
ENV OTEL_SERVICE_NAME="lambda-python-lumigo-container"
ENV LUMIGO_ENABLE_LOGS="true"
ENV DYNAMODB_TABLE_NAME="example-table"
ENV S3_BUCKET_NAME="example-bucket"

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ] 