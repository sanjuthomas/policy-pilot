package com.sanjuthomas.policypilot.observability;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.instrumentation.logback.appender.v1_0.OpenTelemetryAppender;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Wires Spring Boot's OpenTelemetry SDK into Logback's {@link OpenTelemetryAppender} so console
 * logs are also exported over OTLP → collector → Loki.
 *
 * <p>Do not use {@code @ConditionalOnBean(OpenTelemetry.class)} here: for component-scanned beans
 * that condition is evaluated before OTel auto-config registers the SDK bean, so the installer is
 * skipped. Constructor injection is enough to require the bean.
 */
@Component
@ConditionalOnClass(OpenTelemetryAppender.class)
@ConditionalOnProperty(
    name = "management.otlp.logging.endpoint")
public class InstallOpenTelemetryAppender implements InitializingBean {

  private static final Logger log = LoggerFactory.getLogger(InstallOpenTelemetryAppender.class);

  private final OpenTelemetry openTelemetry;

  public InstallOpenTelemetryAppender(OpenTelemetry openTelemetry) {
    this.openTelemetry = openTelemetry;
  }

  @Override
  public void afterPropertiesSet() {
    OpenTelemetryAppender.install(openTelemetry);
    log.info("OpenTelemetry Logback appender installed (OTLP logs → collector → Loki)");
  }
}
