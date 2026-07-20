package com.sanjuthomas.policypilot.observability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class HttpServerMetricsFilterTest {

  @Test
  void recordsDurationForApiPaths() throws Exception {
    MeterRegistry registry = new SimpleMeterRegistry();
    HttpServerMetricsFilter filter = new HttpServerMetricsFilter(registry);
    MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/chat");
    MockHttpServletResponse response = new MockHttpServletResponse();
    FilterChain chain =
        (ServletRequest req, ServletResponse res) -> ((MockHttpServletResponse) res).setStatus(200);

    filter.doFilter(request, response, chain);

    assertEquals(1, registry.find("http.server.request.duration").summaries().size());
    assertTrue(registry.find("http.server.request.duration").summary().totalAmount() >= 0);
  }

  @Test
  void skipsHealth() throws Exception {
    MeterRegistry registry = new SimpleMeterRegistry();
    HttpServerMetricsFilter filter = new HttpServerMetricsFilter(registry);
    MockHttpServletRequest request = new MockHttpServletRequest("GET", "/health");
    MockHttpServletResponse response = new MockHttpServletResponse();
    FilterChain chain = (ServletRequest req, ServletResponse res) -> {};

    filter.doFilter(request, response, chain);

    assertEquals(0, registry.find("http.server.request.duration").summaries().size());
  }
}
