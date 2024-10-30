With the roles now created, you can use their ARNs to assign them to each Lambda function during the creation process. Here’s a complete guide on deploying and setting up each Lambda function, using the roles created in the previous steps.

### Step 1: Get the Role ARNs

Run the following commands to get the ARNs of the roles we created:

```bash
aws iam get-role --role-name logAndTriggerLambdaRole --query 'Role.Arn' --output text
aws iam get-role --role-name triggeredLambdaRole --query 'Role.Arn' --output text
```

Save these ARNs for use in the next step.

### Step 2: Deploy Each Lambda Function

With the deployment packages (`logAndTriggerLambda.zip` and `triggeredLambda.zip`) and the ARNs ready, let’s deploy each Lambda.

1. **Deploy `logAndTriggerLambda`**: Replace `LOG_AND_TRIGGER_ROLE_ARN` with the ARN from the `logAndTriggerLambdaRole`.

    ```bash
    aws lambda create-function --function-name logAndTriggerLambda \
        --runtime nodejs18.x \
        --role LOG_AND_TRIGGER_ROLE_ARN \
        --handler logAndTriggerLambda.handler \
        --zip-file fileb://logAndTriggerLambda.zip \
        --environment Variables="{TRACE_SAMPLING_RATE=1.0}"
    ```

2. **Deploy `triggeredLambda`**: Replace `TRIGGERED_LAMBDA_ROLE_ARN` with the ARN from the `triggeredLambdaRole`.

    ```bash
    aws lambda create-function --function-name triggeredLambda \
        --runtime nodejs18.x \
        --role TRIGGERED_LAMBDA_ROLE_ARN \
        --handler triggeredLambda.handler \
        --zip-file fileb://triggeredLambda.zip \
        --environment Variables="{TRACE_SAMPLING_RATE=1.0}"
    ```

### Step 3: Set Up EventBridge Rule to Connect Lambdas

With the Lambdas deployed, you’ll want to set up an EventBridge rule to trigger the `triggeredLambda` function based on events sent by `logAndTriggerLambda`.

1. **Create the EventBridge Rule**:

    ```bash
    aws events put-rule --name TriggerSecondLambdaRule \
        --event-pattern '{"source": ["custom.myapp"], "detail-type": ["MyAppEvent"]}'
    ```

2. **Add `triggeredLambda` as the Target for the Rule**:

    ```bash
    aws events put-targets --rule TriggerSecondLambdaRule \
        --targets "Id"="1","Arn"="arn:aws:lambda:YOUR_REGION:YOUR_ACCOUNT_ID:function:triggeredLambda"
    ```

3. **Grant EventBridge Permission to Invoke `triggeredLambda`**:

    ```bash
    aws lambda add-permission --function-name triggeredLambda \
        --statement-id AllowEventBridgeInvoke \
        --action "lambda:InvokeFunction" \
        --principal events.amazonaws.com \
        --source-arn arn:aws:events:YOUR_REGION:YOUR_ACCOUNT_ID:rule/TriggerSecondLambdaRule
    ```

### Step 4: Test the Setup

To test, trigger the first Lambda (`logAndTriggerLambda`) and confirm that it logs its message and sends an event to EventBridge, which in turn triggers `triggeredLambda`.

1. **Invoke `logAndTriggerLambda` Directly**:

    ```bash
    aws lambda invoke --function-name logAndTriggerLambda response.json
    ```

2. **Check CloudWatch Logs**: Go to **CloudWatch Logs** in the AWS Console to check the logs for both `logAndTriggerLambda` and `triggeredLambda`. Confirm that:
   - `logAndTriggerLambda` logs its message and sends the event.
   - `triggeredLambda` is triggered and logs the event details it received.

### Optional Step: Update Functions (For Future Changes)

For any updates to the Lambda code, re-zip the modified Lambda files and update them using:

```bash
aws lambda update-function-code --function-name logAndTriggerLambda --zip-file fileb://logAndTriggerLambda.zip
aws lambda update-function-code --function-name triggeredLambda --zip-file fileb://triggeredLambda.zip
```

With these steps, you now have both Lambda functions deployed, connected via EventBridge, and logging through Lumigo with sampling. Let me know if you'd like further customization or assistance with any specific settings!