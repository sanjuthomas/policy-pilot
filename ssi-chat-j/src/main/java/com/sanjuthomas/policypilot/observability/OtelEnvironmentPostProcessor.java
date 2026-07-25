package com.sanjuthomas.policypilot.observability;

import java.util.HashMap;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

/**
 * Honors Python-compatible {@code OTEL_SDK_DISABLED} / {@code OTEL_*} env vars.
 *
 * <p>Micrometer's OTLP metrics registry is <strong>HTTP-only</strong>. The shared Compose mesh sets
 * {@code OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317} (gRPC). This processor remaps
 * metrics (and HTTP log export) to the collector's HTTP port {@code :4318} with the standard
 * {@code /v1/*} paths, while traces keep gRPC on {@code :4317} when the env protocol is gRPC.
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
    boolean sdkDisabled = "true".equalsIgnoreCase(disabled) || "1".equals(disabled);
    if (sdkDisabled) {
      props.put("management.otlp.metrics.export.enabled", "false");
      props.put("management.otlp.logging.export.enabled", "false");
      props.put("management.tracing.enabled", "false");
    }

    String endpoint =
        firstNonBlank(
            System.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            environment.getProperty("OTEL_EXPORTER_OTLP_ENDPOINT"),
            environment.getProperty("management.otlp.metrics.export.url"));
    String protocol =
        firstNonBlank(
            System.getenv("OTEL_EXPORTER_OTLP_PROTOCOL"),
            environment.getProperty("OTEL_EXPORTER_OTLP_PROTOCOL"),
            "grpc");

    if (endpoint != null && !endpoint.isBlank() && !sdkDisabled) {
      String httpBase = toHttpCollectorBase(endpoint);
      // Micrometer OTLP metrics: always HTTP/protobuf on :4318.
      props.put("management.otlp.metrics.export.url", httpBase + "/v1/metrics");
      props.put("management.otlp.metrics.export.protocol", "http/protobuf");
      // Spring Boot OTLP logging: HTTP on :4318 (auto-config needs endpoint + enabled).
      props.put("management.otlp.logging.export.enabled", "true");
      props.put("management.otlp.logging.endpoint", httpBase + "/v1/logs");
      props.put("management.otlp.logging.transport", "http");

      if ("grpc".equalsIgnoreCase(protocol)) {
        props.put("management.otlp.tracing.endpoint", stripTrailingSlash(endpoint));
        props.put("management.otlp.tracing.transport", "grpc");
      } else {
        props.put("management.otlp.tracing.endpoint", httpBase + "/v1/traces");
        props.put("management.otlp.tracing.transport", "http");
      }
    }

    String intervalMs =
        firstNonBlank(
            System.getenv("OTEL_METRIC_EXPORT_INTERVAL"),
            environment.getProperty("OTEL_METRIC_EXPORT_INTERVAL"));
    if (intervalMs != null && !intervalMs.isBlank()) {
      try {
        long ms = Long.parseLong(intervalMs.trim());
        // DurationStyle rejects fractional seconds like "15.0s".
        if (ms % 1000L == 0L) {
          props.put("management.otlp.metrics.export.step", (ms / 1000L) + "s");
        } else {
          props.put("management.otlp.metrics.export.step", ms + "ms");
        }
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

    String serviceName =
        firstNonBlank(
            System.getenv("OTEL_SERVICE_NAME"),
            environment.getProperty("OTEL_SERVICE_NAME"),
            environment.getProperty("spring.application.name"),
            "ssi-chat-j");
    props.put("management.metrics.tags.service", serviceName);
    props.put("management.opentelemetry.resource-attributes.service.name", serviceName);
    props.put("management.otlp.metrics.export.resource-attributes.service.name", serviceName);

    if (!props.isEmpty()) {
      environment
          .getPropertySources()
          .addFirst(new MapPropertySource("otelEnvironmentPostProcessor", props));
    }
  }

  /**
   * Normalize a collector base URL for Micrometer/Spring HTTP OTLP exporters (:4318, no /v1 path).
   */
  static String toHttpCollectorBase(String endpoint) {
    String trimmed = stripTrailingSlash(endpoint);
    for (String suffix : new String[] {"/v1/metrics", "/v1/traces", "/v1/logs"}) {
      if (trimmed.endsWith(suffix)) {
        trimmed = trimmed.substring(0, trimmed.length() - suffix.length());
        break;
      }
    }
    if (trimmed.endsWith(":4317")) {
      trimmed = trimmed.substring(0, trimmed.length() - 4) + "4318";
    }
    return trimmed;
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
