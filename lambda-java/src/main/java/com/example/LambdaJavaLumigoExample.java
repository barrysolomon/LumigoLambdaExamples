import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyRequestEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;

import com.amazonaws.services.secretsmanager.AWSSecretsManager;
import com.amazonaws.services.secretsmanager.AWSSecretsManagerClientBuilder;
import com.amazonaws.services.secretsmanager.model.GetSecretValueRequest;
import com.amazonaws.services.secretsmanager.model.GetSecretValueResult;

import io.lumigo.handlers.LumigoRequestExecutor;
import io.lumigo.handlers.LumigoConfiguration;

import java.util.Map;
import java.util.function.Supplier;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class LambdaJavaLumigoExample implements RequestHandler<Map<String, Object>, String> {

    private static final Logger logger = LogManager.getLogger(LambdaJavaLumigoExample.class);
    private static final String WEATHER_API_KEY_SECRET = "initech-weather-api-key"; // Replace with your actual secret name
    private static final String REGION                 = "us-east-1";               // Replace with your secret's region

    private static String getSecret(String secretName) {
        AWSSecretsManager client = AWSSecretsManagerClientBuilder.standard()
                .withRegion(REGION)
                .build();

        GetSecretValueRequest getSecretValueRequest = new GetSecretValueRequest()
                .withSecretId(secretName);
        GetSecretValueResult getSecretValueResult = client.getSecretValue(getSecretValueRequest);

        // Check if the secret value is stored as a string or binary
        if (getSecretValueResult.getSecretString() != null) {
            return getSecretValueResult.getSecretString();
        } else {
            // If the secret is binary, convert it to a string (if applicable)
            return new String(getSecretValueResult.getSecretBinary().array());
        }
    }

    static {
        String lumigo_token = System.getenv("LUMIGO_TRACER_TOKEN");
        if (lumigo_token == null || lumigo_token.isEmpty()) {
            logger.error("Lumigo token is not set in environment variables.");
        }
        LumigoConfiguration.builder()
            .token(lumigo_token)
            .build()
            .init();

        logger.info("Lumigo tracer initialized.");
    }

    @Override
    public String handleRequest(Map<String, Object> event, Context context) {
        Supplier<String> supplier = () -> {

            // Process the JSON event
            logger.info("Lambda function intialized, processing event: " + event);

            // Get API key from environment variable
            String weather_api_key = System.getenv("OPENWEATHER_API_KEY");
            if (weather_api_key == null || weather_api_key.isEmpty()) {
                logger.warn("API key is not set in environment variables. Trying Secret's manager...");
                weather_api_key = getSecret(WEATHER_API_KEY_SECRET);
                if (weather_api_key == null || weather_api_key.isEmpty()) {
                    logger.error("API key is not set in secrets manager.");
                }
            }

            try {

                URL url = new URL("https://api.openweathermap.org/data/2.5/weather?appid=" + weather_api_key + "&lat=-40.7128&lon=-74.0060&units=metric");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.connect();

                // Read response
                BufferedReader rd = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = rd.readLine()) != null) {
                    response.append(line);
                }
                rd.close();

                // Construct response
                APIGatewayProxyResponseEvent responseEvent = new APIGatewayProxyResponseEvent();
                responseEvent.setStatusCode(201);
                responseEvent.setBody("Weather data fetched and stored successfully.");
                logger.info("Weather data fetched and stored successfully.");

                return responseEvent.getBody();

            } catch (Exception e) {

                logger.error("Error fetching weather data: {}", e.getMessage(), e);
                APIGatewayProxyResponseEvent errorResponse = new APIGatewayProxyResponseEvent();
                errorResponse.setStatusCode(500);
                errorResponse.setBody("Error fetching weather data: " + e.getMessage());
                return errorResponse.getBody();

            }

        };
        return LumigoRequestExecutor.execute(event, context, supplier);
    }
}
