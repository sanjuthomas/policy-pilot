package com.policypilot.chatj.observability;

import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Set;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Records {@code http.server.request.duration} (ms) with the same attribute keys as Python
 * telemetry so OpenSLO HTTP success / ≤5s latency queries stay portable. Includes a 5000ms SLO
 * boundary for the chat latency SLI.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 20)
public class HttpServerMetricsFilter extends OncePerRequestFilter {

  private static final Set<String> EXCLUDED =
      Set.of("/health", "/actuator", "/actuator/health");

  private final MeterRegistry meterRegistry;

  public HttpServerMetricsFilter(MeterRegistry meterRegistry) {
    this.meterRegistry = meterRegistry;
  }

  @Override
  protected boolean shouldNotFilter(HttpServletRequest request) {
    String path = request.getRequestURI();
    if (path == null) {
      return true;
    }
    return EXCLUDED.contains(path) || path.startsWith("/actuator/");
  }

  @Override
  protected void doFilterInternal(
      HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
      throws ServletException, IOException {
    long startNs = System.nanoTime();
    try {
      filterChain.doFilter(request, response);
    } finally {
      double durationMs = (System.nanoTime() - startNs) / 1_000_000.0;
      String path = request.getRequestURI();
      DistributionSummary.builder("http.server.request.duration")
          .baseUnit("ms")
          .serviceLevelObjectives(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
          .tags(
              Tags.of(
                  "http.request.method", request.getMethod(),
                  "http.response.status_code", String.valueOf(response.getStatus()),
                  "url.path", path == null ? "" : path))
          .register(meterRegistry)
          .record(durationMs);
    }
  }
}
