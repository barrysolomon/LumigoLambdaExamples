# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.11

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Copy requirements.txt
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt

ENV LUMIGO_TRACER_TOKEN="t_5a4ddb7fde3d4e888646c"

# Set the CMD to your handler (function) name
CMD ["app.lambda_handler"]
