package com.sanjuthomas.policypilot.observability;

import io.micrometer.core.instrument.config.MeterFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ObservabilityConfig {

  /**
   * Prefer the OTel-shaped HTTP duration series ({@link HttpServerMetricsFilter}); drop Spring
   * Boot's default {@code http.server.requests} to avoid double-counting noise in the collector.
   */
  @Bean
  MeterFilter denySpringHttpServerRequests() {
    return MeterFilter.denyNameStartsWith("http.server.requests");
  }
}
