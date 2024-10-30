const AWS = require('aws-sdk');
const eventBridge = new AWS.EventBridge();

const lumigo = require('@lumigo/tracer')();

// Configuration object for user-specific settings
const config = {
    handler: 'myHandler',  // Can be a string (name of function) or function reference
    traceSamplingRate: parseFloat(process.env.TRACE_SAMPLING_RATE) || 1.0,
    warmupSource: 'serverless-plugin-warmup',  // Filter string to identify warm-up requests.  Defaults to serverless plugin
    debug: (process.env.LUMIGO_DEBUG?.toLowerCase() === 'true') || false
};

// Main handler function
const myHandler = async (event, context) => {
    console.log("Logging from the first Lambda function.");

    // Prepare EventBridge parameters, passing event data
    const params = {
        Entries: [
            {
                Source: 'custom.myapp',
                DetailType: 'MyAppEvent',
                Detail: JSON.stringify({
                    message: "Triggered by the first Lambda",
                    eventData: event // Pass the Lambda event data to EventBridge
                }),
                EventBusName: 'default'
            }
        ]
    };

    try {
        const result = await eventBridge.putEvents(params).promise();
        console.log("Event sent to EventBridge:", result);
    } catch (error) {
        console.error("Failed to send event:", error);
    }

    return 'Event triggered successfully';
};

// Wrapper handler that conditionally applies tracing on each invocation
exports.handler = async (event, context) => {

    // Check if the request should be sampled based on the rate and warm-up filter
    const shouldTrace = () => {
        if (context?.clientContext?.custom?.source === config.warmupSource) {
            if (config.debug)
                console.log('WarmUp - Lambda is warm!');
            return false;
        }
        return Math.random() <= config.traceSamplingRate;
    };

    // Function to dynamically resolve the handler
    const resolveHandlerFunction = (configHandler) => {
        if (typeof configHandler === 'function') {
            return configHandler;  // Direct function reference
        }
        if (typeof configHandler === 'string') {
            // Attempt to find the function in `module.exports`
            if (module.exports[configHandler]) {
                return module.exports[configHandler];
            }
            // Attempt to find the function in the current scope (e.g., declared in file but not exported)
            try {
                return eval(configHandler);  // Dynamically evaluate the function by name
            } catch (error) {
                if (config.debug)
                    console.error(`Handler function "${configHandler}" not found.`);
                throw new Error(`Handler function "${configHandler}" not found.`);
            }
        }
        throw new Error('Invalid handler configuration: handler must be a function or a string.');
    };

    const requestId = context.awsRequestId;
    const handlerFunction = resolveHandlerFunction(config.handler);

    // To trace or not to trace
    const traceDecision = shouldTrace();
    if (config.debug)
        console.log(`Sampling Info - Request ID: ${requestId}, Trace Sampling Rate: ${config.traceSamplingRate}, Tracing Enabled: ${traceDecision}`);

    if (traceDecision) {
        console.debug(`Tracing ${handlerFunction.name || config.handler} with Lumigo.`);
        const tracedHandler = lumigo.trace(handlerFunction);
        return tracedHandler(event, context);
    } else {
        console.debug(`NOT Tracing ${handlerFunction.name || config.handler} with Lumigo.`);
        return handlerFunction(event, context);
    }
};
