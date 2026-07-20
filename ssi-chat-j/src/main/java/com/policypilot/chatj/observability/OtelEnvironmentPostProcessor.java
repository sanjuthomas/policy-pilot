package com.policypilot.chatj.observability;

import java.util.HashMap;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

/**
 * Honors Python-compatible {@code OTEL_SDK_DISABLED} / {@code OTEL_*} env vars for Micrometer OTLP
 * export (metrics + traces). Does not enable a Prometheus scrape endpoint.
 */
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class OtelEnvironmentPostProcessor implements EnvironmentPostProcessor {

  @Override
  public void postProcessEnvironment(
      ConfigurableEnvironment environment, SpringApplication application) {
    Map<String, Object> props = new HashMap<>();

    String disabled =
        firstNonBlank(
            System.getenv("OTEL_SDK_DISABLED"), environment.getProperty("OTEL_SDK_DISABLED"));
    if ("true".equalsIgnoreCase(disabled) || "1".equals(disabled)) {
      props.put("management.otlp.metrics.export.enabled", "false");
      props.put("management.tracing.enabled", "false");
    }

    String endpoint =
        firstNonBlank(
            System.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            environment.getProperty("OTEL_EXPORTER_OTLP_ENDPOINT"),
            environment.getProperty("management.otlp.metrics.export.url"));
    if (endpoint != null && !endpoint.isBlank()) {
      String trimmed = stripTrailingSlash(endpoint);
      // Micrometer OTLP: grpc uses host:port; http/protobuf needs /v1/metrics path.
      String protocol =
          firstNonBlank(
              System.getenv("OTEL_EXPORTER_OTLP_PROTOCOL"),
              environment.getProperty("OTEL_EXPORTER_OTLP_PROTOCOL"),
              environment.getProperty("management.otlp.metrics.export.protocol"),
              "grpc");
      if ("grpc".equalsIgnoreCase(protocol)) {
        props.put("management.otlp.metrics.export.url", trimmed);
        props.put("management.otlp.metrics.export.protocol", "grpc");
        props.put("management.otlp.tracing.endpoint", trimmed);
        props.put("management.otlp.tracing.transport", "grpc");
      } else {
        String metricsUrl =
            trimmed.endsWith("/v1/metrics") ? trimmed : trimmed + "/v1/metrics";
        String tracesUrl = trimmed.endsWith("/v1/traces") ? trimmed : trimmed + "/v1/traces";
        props.put("management.otlp.metrics.export.url", metricsUrl);
        props.put("management.otlp.metrics.export.protocol", "http/protobuf");
        props.put("management.otlp.tracing.endpoint", tracesUrl);
      }
    }

    String intervalMs =
        firstNonBlank(
            System.getenv("OTEL_METRIC_EXPORT_INTERVAL"),
            environment.getProperty("OTEL_METRIC_EXPORT_INTERVAL"));
    if (intervalMs != null && !intervalMs.isBlank()) {
      try {
        long ms = Long.parseLong(intervalMs.trim());
        props.put("management.otlp.metrics.export.step", (ms / 1000.0) + "s");
      } catch (NumberFormatException ignored) {
        // leave Spring default
      }
    }

    String envName =
        firstNonBlank(
            System.getenv("OTEL_DEPLOYMENT_ENVIRONMENT"),
            environment.getProperty("OTEL_DEPLOYMENT_ENVIRONMENT"),
            environment.getProperty("management.metrics.tags.deployment.environment"));
    if (envName != null) {
      props.put("management.metrics.tags.deployment.environment", envName);
    }

    if (!props.isEmpty()) {
      environment
          .getPropertySources()
          .addFirst(new MapPropertySource("otelEnvironmentPostProcessor", props));
    }
  }

  private static String firstNonBlank(String... values) {
    if (values == null) {
      return null;
    }
    for (String value : values) {
      if (value != null && !value.isBlank()) {
        return value;
      }
    }
    return null;
  }

  private static String stripTrailingSlash(String value) {
    if (value.endsWith("/")) {
      return value.substring(0, value.length() - 1);
    }
    return value;
  }
}
