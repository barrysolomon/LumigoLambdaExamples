import com.amazonaws.client.builder.AwsClientBuilder;
import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.secretsmanager.AWSSecretsManager;
import com.amazonaws.services.secretsmanager.AWSSecretsManagerClientBuilder;
import com.amazonaws.services.secretsmanager.model.GetSecretValueRequest;
import com.amazonaws.services.secretsmanager.model.GetSecretValueResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.lumigo.handlers.LumigoConfiguration;
import io.lumigo.handlers.LumigoRequestExecutor;
import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.function.Supplier;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class LambdaJavaLumigoExampleWeather implements RequestHandler<Map<String, Object>, String> {

    private static final Logger logger = LogManager.getLogger(LambdaJavaLumigoExampleWeather.class);
    private static final String WEATHER_API_KEY_SECRET = "initech-weather-api-key";
    private static final String BUCKET_NAME = "initech-weather-data-bucket";
    private static final String REGION = "us-east-1";
    private static final String S3_ENDPOINT = "https://s3.us-east-1.amazonaws.com";

    private final AmazonS3 s3Client = AmazonS3ClientBuilder.standard()
            // .withRegion(REGION)
            .withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(S3_ENDPOINT, REGION))
            .build();

    private boolean hasS3Permissions = true;

    // Check for S3 permissions on initialization
    public LambdaJavaLumigoExampleWeather() {
    }

    // Method to test if Lambda has sufficient S3 permissions
    private void checkS3Permissions() {
        try {
            if (s3Client.doesBucketExistV2(BUCKET_NAME)) {
                hasS3Permissions = true;
                logger.info("S3 permissions verified.");
            } else {
                logger.warn("Bucket does not exist, permissions might still be insufficient.");
            }
        } catch (Exception e) {
            hasS3Permissions = false;
            logger.warn("Insufficient S3 permissions: " + e.getMessage() + ". S3 storage logic will not be executed.");
        }
    }    

    // Create the S3 bucket if it doesn’t exist
    private void createBucketIfNotExists(String bucketName) {
        if (hasS3Permissions && !s3Client.doesBucketExistV2(bucketName)) {
            logger.info("Bucket does not exist. Creating bucket: " + bucketName);
            s3Client.createBucket(bucketName);
        }
    }

    // Store the API response in S3 as JSON
    private void storeResponseInS3(String bucketName, String responseData) {
        if (!hasS3Permissions) {
            logger.warn("Skipping S3 storage logic due to insufficient permissions.");
            return;
        }

        String objectKey = "weather-response.json";
        PutObjectRequest putRequest = new PutObjectRequest(bucketName, objectKey,
                new ByteArrayInputStream(responseData.getBytes(StandardCharsets.UTF_8)), null);
        s3Client.putObject(putRequest);
        logger.info("Stored response in S3 at s3://" + bucketName + "/" + objectKey);
    }

    // Fetch the secret from AWS Secrets Manager
    private static String getSecret(String secretName) {
        AWSSecretsManager client = AWSSecretsManagerClientBuilder.standard()
                .withRegion(REGION)
                .build();

        GetSecretValueRequest getSecretValueRequest = new GetSecretValueRequest()
                .withSecretId(secretName);
        GetSecretValueResult getSecretValueResult = client.getSecretValue(getSecretValueRequest);

        if (getSecretValueResult.getSecretString() != null) {
            return getSecretValueResult.getSecretString();
        } else {
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

            String weatherApiKey = System.getenv("OPENWEATHER_API_KEY");
            if (weatherApiKey == null || weatherApiKey.isEmpty()) {
                logger.warn("API key is not set in environment variables. Trying Secrets Manager...");
                weatherApiKey = getSecret(WEATHER_API_KEY_SECRET);
                if (weatherApiKey == null || weatherApiKey.isEmpty()) {
                    logger.error("API key is not set in Secrets Manager.");
                }
            }

            try {
                URL url = new URL("https://api.openweathermap.org/data/2.5/weather?appid=" + weatherApiKey + "&lat=-40.7128&lon=-74.0060&units=metric");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.connect();

                BufferedReader rd = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder responseBuilder = new StringBuilder();
                String line;
                while ((line = rd.readLine()) != null) {
                    responseBuilder.append(line);
                }
                rd.close();

                // Format response as JSON
                ObjectMapper objectMapper = new ObjectMapper();
                ObjectNode jsonResponse = objectMapper.createObjectNode();
                jsonResponse.put("message", "Weather data fetched successfully.");
                jsonResponse.put("data", responseBuilder.toString());

                String jsonString = jsonResponse.toString();
                logger.info("Weather API response: " + jsonString);

                // Store the response in S3
                checkS3Permissions();
                createBucketIfNotExists(BUCKET_NAME);
                storeResponseInS3(BUCKET_NAME, jsonString);

                // Return JSON response
                APIGatewayProxyResponseEvent responseEvent = new APIGatewayProxyResponseEvent();
                responseEvent.setStatusCode(200);
                responseEvent.setHeaders(Map.of("Content-Type", "application/json"));
                responseEvent.setBody(jsonString);

                return responseEvent.getBody();

            } catch (Exception e) {
                logger.error("Error fetching weather data: {}", e.getMessage(), e);

                // Construct JSON error response
                ObjectMapper objectMapper = new ObjectMapper();
                ObjectNode errorResponse = objectMapper.createObjectNode();
                errorResponse.put("message", "Error fetching weather data");
                errorResponse.put("error", e.getMessage());

                String errorString = errorResponse.toString();
                logger.info("Error response: " + errorString);

                APIGatewayProxyResponseEvent errorEvent = new APIGatewayProxyResponseEvent();
                errorEvent.setStatusCode(500);
                errorEvent.setHeaders(Map.of("Content-Type", "application/json"));
                errorEvent.setBody(errorString);

                return errorEvent.getBody();
            }
        };

        return LumigoRequestExecutor.execute(event, context, supplier);
    }
}
