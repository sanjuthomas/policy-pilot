package com.sanjuthomas.policypilot;

import com.sanjuthomas.policypilot.observability.OtelEnvironmentPostProcessor;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.boot.env.EnvironmentPostProcessorApplicationListener;
import org.springframework.boot.env.EnvironmentPostProcessorsFactory;

@SpringBootApplication
@ConfigurationPropertiesScan
public class ChatJApplication {

  public static void main(String[] args) {
    SpringApplication app = new SpringApplication(ChatJApplication.class);
    // spring-boot-maven-plugin lifts META-INF out of BOOT-INF/classes, so
    // META-INF/spring/*.imports is not visible to LaunchedClassLoader. Register
    // the OTEL remapper explicitly (Compose gRPC :4317 → HTTP :4318 for Micrometer).
    app.addListeners(
        EnvironmentPostProcessorApplicationListener.with(
            EnvironmentPostProcessorsFactory.of(OtelEnvironmentPostProcessor.class.getName())));
    app.run(args);
  }
}
