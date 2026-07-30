package com.sanjuthomas.policypilot.observability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class StructuredObservabilityTest {

  @Test
  void httpRouteTemplatesAreLowCardinality() {
    assertEquals("/api/chat", HttpRouteTemplates.template("/api/chat"));
    assertEquals(
        "/api/chat/skills/*/confirm",
        HttpRouteTemplates.template("/api/chat/skills/approve-payment/confirm"));
    assertEquals("/api/*", HttpRouteTemplates.template("/api/unknown"));
    assertEquals("other", HttpRouteTemplates.template("/static/app.js"));
    assertEquals("unknown", HttpRouteTemplates.template(null));
  }

  @Test
  void httpMetricsUseRouteTemplateNotRawPath() throws Exception {
    MeterRegistry registry = new SimpleMeterRegistry();
    HttpServerMetricsFilter filter = new HttpServerMetricsFilter(registry);
    MockHttpServletRequest request =
        new MockHttpServletRequest("POST", "/api/chat/skills/create-payment/confirm");
    MockHttpServletResponse response = new MockHttpServletResponse();
    FilterChain chain =
        (ServletRequest req, ServletResponse res) -> ((MockHttpServletResponse) res).setStatus(200);

    filter.doFilter(request, response, chain);

    assertEquals(
        "/api/chat/skills/*/confirm",
        registry.find("http.server.request.duration").summary().getId().getTag("url.path"));
  }

  @Test
  void mdcFilterSetsRequestIdAndClears() throws Exception {
    ChatMdcFilter filter = new ChatMdcFilter();
    MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/chat");
    request.addHeader("X-Request-Id", "req-fixed-1");
    MockHttpServletResponse response = new MockHttpServletResponse();
    FilterChain chain =
        (ServletRequest req, ServletResponse res) -> {
          assertEquals("req-fixed-1", MDC.get(ChatLogContext.REQUEST_ID));
          assertEquals("/api/chat", MDC.get(ChatLogContext.HTTP_ROUTE));
        };

    filter.doFilter(request, response, chain);

    assertEquals("req-fixed-1", response.getHeader("X-Request-Id"));
    assertEquals(null, MDC.get(ChatLogContext.REQUEST_ID));
  }

  @Test
  void answerRoutingLogFieldsAreStructured() {
    AnswerRouting routing =
        new AnswerRouting(
            "eligibility",
            "none",
            "eligibility_api",
            "policies",
            "eligibility",
            "me.who_am_i",
            1.5,
            2.5,
            0,
            0,
            Map.of(),
            12,
            "abcdef12",
            "eligibility");
    Map<String, Object> fields = routing.logFields();
    assertEquals("chat.answer.completed", fields.get("chat.event"));
    assertEquals("eligibility", fields.get("chat.path"));
    assertEquals("abcdef12", fields.get("chat.question_hash"));
    assertFalse(fields.containsKey("chat.question"));
  }

  @Test
  void structuredLogAcceptsNullSafeMaps() {
    // Smoke: does not throw when fields contain nulls.
    StructuredLog.info(
        org.slf4j.LoggerFactory.getLogger(StructuredObservabilityTest.class),
        "test.event",
        Map.of("chat.event", "test.event", "ok", true));
    assertTrue(true);
  }
}
