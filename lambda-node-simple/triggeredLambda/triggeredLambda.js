const lumigo = require('@lumigo/tracer'); // Require Lumigo

// Sampling rate from environment or default to 100%
const TRACE_SAMPLING_RATE = parseFloat(process.env.TRACE_SAMPLING_RATE) || 1.0;

// Main handler function
const myHandler = async (event, context) => {
    
    if (context?.clientContext?.custom?.source === 'serverless-plugin-warmup') {
        console.log('WarmUp - Lambda is warm!');
        return 'Lambda is warm!';
    }

    console.log("Triggered Lambda received an event:", JSON.stringify(event, null, 2));
    return 'Event processed';
};

// Decide if the request should be traced based on sampling rate
const shouldTrace = () => {
    return Math.random() < TRACE_SAMPLING_RATE;
};

// Export the handler with conditional tracing
exports.handler = async (event, context) => {
    if (shouldTrace()) {
        console.log('Tracing this request with Lumigo.');
        return lumigo.trace(myHandler)(event, context);
    } else {
        console.log('Not tracing this request (sampled out).');
        return myHandler(event, context);
    }
};
