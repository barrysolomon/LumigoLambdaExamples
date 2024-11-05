const AWS = require('aws-sdk');
const eventBridge = new AWS.EventBridge();

const lumigo = require('@lumigo/tracer')();

// Configuration object for user-specific settings
var config = {
    handler: process.env.LUMIGO_ORIGINAL_HANDLER || 'myHandler',  // Can be a string (name of function) or function reference
    traceSamplingRate: parseFloat(process.env.LUMIGO_TRACE_SAMPLING_RATE) || 1.0,
    warmupSource: process.env.LUMIGO_WARMUP_SOURCE || 'serverless-plugin-warmup',  // Filter string to identify warm-up requests
    traceCondition: process.env.LUMIGO_TRACE_CONDITIONS || '{}', // e.g., '{"field": "event.path", "operator": "contains", "value": "/api/trace"}'
    debug: (process.env.LUMIGO_DEBUG?.toLowerCase() === 'true') || false
};

// Wrapper handler with conditional tracing logic
exports.handler = async (event, context) => {

    // Utility function to safely get nested properties
    const getNestedProperty = (obj, path) => {
        return path.split('.').reduce((acc, part) => acc && acc[part], obj);
    };

    // Parse and validate traceCondition from config
    const parseTraceCondition = () => {
        try {
            const condition = JSON.parse(config.traceCondition);
            if (typeof condition === 'object' && condition !== null &&
                ['field', 'operator', 'value'].every(key => key in condition)) {
                return condition;
            } else {
                if (config.debug) console.warn("Invalid TRACE_CONDITIONS format. Using default empty object.");
                return {};
            }
        } catch (error) {
            console.warn(`Failed to parse TRACE_CONDITIONS JSON (${config.traceCondition}). Using default empty object.`);
            return {};
        }
    };

    // String matching functions
    const stringMatch = {
        exact: (str1, str2) => str1 === str2,
        startswith: (str1, str2) => str1.startsWith(str2),
        endswith: (str1, str2) => str1.endsWith(str2),
        includes: (str1, str2) => str1.includes(str2),
        contains: (str1, str2) => str1.includes(str2),
        notexact: (str1, str2) => str1 !== str2,
        notstartswith: (str1, str2) => !str1.startsWith(str2),
        notendswith: (str1, str2) => !str1.endsWith(str2),
        notincludes: (str1, str2) => !str1.includes(str2),
        notcontains: (str1, str2) => !str1.includes(str2),
        regex: (str, regexPattern) => {
            const [_, pattern, flags] = regexPattern.match(/\/(.+?)\/([a-z]*)$/) || [];
            return new RegExp(pattern || regexPattern, flags).test(str);
        }
    };

    // Determine if the request should be traced
    const shouldTrace = () => {

        // Event-based condition check
        const { field, operator, value } = traceCondition;
        if (field && operator && value) {
            const fieldValue = getNestedProperty(event, field);
            if (fieldValue === undefined) {
                if (config.debug) console.log(`Field ${field} not found in event.`);
                return false;
            }

            if (stringMatch[operator]) {
                if (stringMatch[operator](fieldValue, value)) {
                    if (config.debug) console.log(`Trace Condition Match: Field "${field}" with value "${fieldValue}" ${operator} "${value}".`);
                    return true;
                }
                else {
                    if (config.debug) console.log(`Trace Condition Failed Match: Field "${field}" with value "${fieldValue}" ${operator} "${value}".`);
                    return false;
                }
            }

            if (config.debug) console.log(`Unknown or invalid operator "${operator}".`);
            return false;
        }

        // Warm-up check
        if (context?.clientContext?.custom?.source === config.warmupSource) {
            if (config.debug) console.log('WarmUp - Lambda is warm!');
            return false;
        }

        // Sampling check
        if (Math.random() > config.traceSamplingRate) {
            if (config.debug) console.log('Request not sampled based on traceSamplingRate');
            return false;
        }

        // Default to trace if sampling passes and no specific conditions are defined
        if (config.debug) console.log('Request traced by default (sampling passes, no condition specified)');
        return true;
    };

    // Function to dynamically resolve the handler
    const resolveHandlerFunction = (configHandler) => {
        if (typeof configHandler === 'function') {
            return configHandler;  // Direct function reference
        }
        if (typeof configHandler === 'string') {
            try {
                return module.exports[configHandler] || eval(configHandler);
            } catch (error) {
                if (config.debug) console.error(`Handler function "${configHandler}" not found.`);
                throw new Error(`Handler function "${configHandler}" not found.`);
            }
        }
        throw new Error('Invalid handler configuration: handler must be a function or a string.');
    };

    const requestId = context.awsRequestId;
    const handlerFunction = resolveHandlerFunction(config.handler);

    const traceCondition = parseTraceCondition();

    // Trace decision
    const traceDecision = shouldTrace();
    if (config.debug) console.log(`Sampling Info - Request ID: ${requestId}, Trace Sampling Rate: ${config.traceSamplingRate}, Tracing Enabled: ${traceDecision}`);

    // Execute with or without tracing
    if (traceDecision) {
        if (config.debug) console.log(`Tracing ${handlerFunction.name || config.handler} with Lumigo.`);
        return lumigo.trace(handlerFunction)(event, context);
    } else {
        if (config.debug) console.log(`NOT Tracing ${handlerFunction.name || config.handler} with Lumigo.`);
        return handlerFunction(event, context);
    }

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

