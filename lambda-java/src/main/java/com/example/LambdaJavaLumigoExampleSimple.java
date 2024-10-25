import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import io.lumigo.handlers.LumigoConfiguration;
import io.lumigo.handlers.LumigoRequestExecutor;
import java.util.Map;
import java.util.function.Supplier;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;




public class LambdaJavaLumigoExampleSimple implements RequestHandler<Map<String, Object>, String> {

    private static final Logger logger = LogManager.getLogger(LambdaJavaLumigoExampleSimple.class);

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

            logger.error("Java Lambda Handler Successfully called.");

            return "Java Lambda Handler Successfully called.";
            
        };

        return LumigoRequestExecutor.execute(event, context, supplier);
    }
}
