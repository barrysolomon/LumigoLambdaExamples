import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import io.lumigo.handlers.LumigoRequestExecutor;
import io.lumigo.handlers.LumigoConfiguration;

import java.util.function.Supplier;

public class WeatherLambdaJavaSimple implements RequestHandler<String, String> {

        static{
            LumigoConfiguration.builder().token("t_5a4ddb7fde3d4e888646c").build().init();
        }

        @Override
        public String handleRequest(String event, Context context) {
            Supplier<String> supplier = () -> {
                //Your lambda code
                return "";
            };
            return LumigoRequestExecutor.execute(event, context, supplier);
        }
    }