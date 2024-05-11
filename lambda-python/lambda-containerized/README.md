To create a Python containerized AWS Lambda function, you'll need to follow these steps:

1. **Create a Dockerfile** for the Lambda function.
2. **Write your Lambda function code**.
3. **Build the Docker image**.
4. **Push the Docker image to Amazon ECR (Elastic Container Registry)**.
5. **Deploy the Lambda function using the container image**.

Here's a step-by-step guide:

### Step 1: Create a Dockerfile

Create a file named `Dockerfile` with the following content:

```Dockerfile
# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.8

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (function) name
CMD ["app.lambda_handler"]
```

### Step 2: Write Your Lambda Function Code

Create a file named `app.py` with your Lambda function code:

```python
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps(event)
    }
```

### Step 3: Build the Docker Image

Open your terminal and navigate to the directory containing your `Dockerfile` and `app.py`. Then, build the Docker image:

```sh
docker build --platform linux/amd64 -t my-lambda-function .
```

### Step 4: Push the Docker Image to Amazon ECR

1. **Login to ECR**:
   
   ```sh
   aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.<your-region>.amazonaws.com
   ```

2. **Create an ECR repository**:

   ```sh
   aws ecr create-repository --repository-name my-lambda-repo
   ```

3. **Tag your Docker image**:

   ```sh
   docker tag my-lambda-function:latest <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/my-lambda-repo:latest
   ```

4. **Push the Docker image to ECR**:

   ```sh
   docker push <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/my-lambda-repo:latest
   ```

### Step 5: Deploy the Lambda Function Using the Container Image

1. **Create the Lambda function**:

   ```sh
   aws lambda create-function \
     --function-name my-container-lambda \
     --package-type Image \
     --code ImageUri=<your-account-id>.dkr.ecr.<your-region>.amazonaws.com/my-lambda-repo:latest \
     --role arn:aws:iam::<your-account-id>:role/<your-lambda-execution-role>
   ```

2. **Test your Lambda function**:

   You can test your Lambda function via the AWS Management Console or using the AWS CLI:

   ```sh
   aws lambda invoke --function-name my-container-lambda output.json
   ```

### Summary of Key Commands

- **Build Docker Image**: `docker build -t my-lambda-function .`
- **Login to ECR**: `aws ecr get-login-password ...`
- **Create ECR Repository**: `aws ecr create-repository --repository-name my-lambda-repo`
- **Tag Docker Image**: `docker tag my-lambda-function:latest ...`
- **Push Docker Image**: `docker push ...`
- **Create Lambda Function**: `aws lambda create-function ...`
- **Test Lambda Function**: `aws lambda invoke ...`

These steps should help you set up and deploy a Python containerized Lambda function successfully. If you need to customize the Lambda function or the Docker image, you can modify the `app.py` and `Dockerfile` accordingly.