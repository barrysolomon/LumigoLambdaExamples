import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyRequestEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.function.Supplier;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import io.lumigo.handlers.LumigoRequestExecutor;

public class WeatherLambdaJava implements RequestHandler<APIGatewayProxyRequestEvent, APIGatewayProxyResponseEvent> {
    private static final Logger logger = LogManager.getLogger(WeatherLambdaJava.class);

    @Override
    public APIGatewayProxyResponseEvent handleRequest(APIGatewayProxyRequestEvent event, Context context) {

        logger.info("Lambda function started");
        logger.debug("Event details: {}", event);

        Supplier<APIGatewayProxyResponseEvent> supplier = () -> {       
            
            logger.info("Fetching weather data...");

            // Get API key from environment variable
            String apiKey = System.getenv("OPENWEATHER_API_KEY");
            if (apiKey == null || apiKey.isEmpty()) {
                logger.warn("API key is not set in environment variables.");
                apiKey = "23486a8b00ef906519643b2a87ffc3c6"; // Default key (for testing)
            }

            try {
                URL url = new URL("https://api.openweathermap.org/data/2.5/weather?appid=" + apiKey + "&lat=-40.7128&lon=-74.0060&units=metric");
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

                return responseEvent;

            } catch (Exception e) {
                logger.error("Error fetching weather data: {}", e.getMessage(), e);
                APIGatewayProxyResponseEvent errorResponse = new APIGatewayProxyResponseEvent();
                errorResponse.setStatusCode(500);
                errorResponse.setBody("Error fetching weather data: " + e.getMessage());
                return errorResponse;
            }

        };
        return LumigoRequestExecutor.execute(event, context, supplier);
    }
}
