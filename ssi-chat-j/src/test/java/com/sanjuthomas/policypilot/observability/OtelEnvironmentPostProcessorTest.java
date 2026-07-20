package com.sanjuthomas.policypilot.observability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import io.micrometer.core.instrument.config.MeterFilter;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.boot.SpringApplication;
import org.springframework.mock.env.MockEnvironment;

class OtelEnvironmentPostProcessorTest {

  @Test
  void postProcessDoesNotThrow() {
    MockEnvironment env = new MockEnvironment();
    new OtelEnvironmentPostProcessor().postProcessEnvironment(env, new SpringApplication());
    assertNotNull(env.getPropertySources());
  }

  @Test
  void disablesExportWhenOtelSdkDisabled() {
    MockEnvironment env = new MockEnvironment();
    env.setProperty("OTEL_SDK_DISABLED", "true");
    new OtelEnvironmentPostProcessor().postProcessEnvironment(env, new SpringApplication());
    assertEquals("false", env.getProperty("management.otlp.metrics.export.enabled"));
    assertEquals("false", env.getProperty("management.tracing.enabled"));
  }

  @Test
  void mapsGrpcEndpoint() {
    MockEnvironment env = new MockEnvironment();
    env.setProperty("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317");
    env.setProperty("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc");
    new OtelEnvironmentPostProcessor().postProcessEnvironment(env, new SpringApplication());
    assertEquals("http://otel-collector:4317", env.getProperty("management.otlp.metrics.export.url"));
    assertEquals("grpc", env.getProperty("management.otlp.metrics.export.protocol"));
  }

  @Test
  void mapsHttpProtobufPaths() {
    MockEnvironment env = new MockEnvironment();
    env.setProperty("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318");
    env.setProperty("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf");
    new OtelEnvironmentPostProcessor().postProcessEnvironment(env, new SpringApplication());
    assertEquals(
        "http://otel-collector:4318/v1/metrics",
        env.getProperty("management.otlp.metrics.export.url"));
    assertEquals(
        "http://otel-collector:4318/v1/traces",
        env.getProperty("management.otlp.tracing.endpoint"));
  }

  @Test
  void mapsExportIntervalAndEnvironment() {
    MockEnvironment env = new MockEnvironment();
    env.setProperty("OTEL_METRIC_EXPORT_INTERVAL", "15000");
    env.setProperty("OTEL_DEPLOYMENT_ENVIRONMENT", "development");
    new OtelEnvironmentPostProcessor().postProcessEnvironment(env, new SpringApplication());
    assertEquals("15.0s", env.getProperty("management.otlp.metrics.export.step"));
    assertEquals(
        "development", env.getProperty("management.metrics.tags.deployment.environment"));
  }

  @Test
  void denyFilterBeanPresent() {
    MeterFilter filter = new ObservabilityConfig().denySpringHttpServerRequests();
    assertNotNull(filter);
  }

  @Test
  void answerRoutingLogFieldsIncludeEvent() {
    AnswerRouting routing =
        new AnswerRouting(
            "eligibility",
            "none",
            "eligibility_api",
            "events",
            "eligibility",
            "id",
            1.0,
            2.0,
            0,
            0,
            Map.of("vector", 2),
            3,
            "abc",
            null);
    Map<String, Object> fields = routing.logFields();
    assertEquals("chat.answer.completed", fields.get("chat.event"));
    assertEquals(2, fields.get("chat.source_vector"));
  }
}
