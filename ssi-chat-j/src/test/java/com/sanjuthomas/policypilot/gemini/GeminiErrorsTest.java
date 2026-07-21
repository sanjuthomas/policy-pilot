package com.sanjuthomas.policypilot.gemini;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class GeminiErrorsTest {

  @Test
  void detectsResourceExhaustedMessage() {
    assertTrue(
        GeminiErrors.isRateLimit(
            new RuntimeException(
                "Failed to generate content: RESOURCE_EXHAUSTED: Resource exhausted")));
  }

  @Test
  void detectsNestedCause() {
    RuntimeException nested =
        new RuntimeException("io.grpc.StatusRuntimeException: RESOURCE_EXHAUSTED: try again");
    assertTrue(GeminiErrors.isRateLimit(new IllegalStateException("Spring AI routing failed", nested)));
  }

  @Test
  void detects429QuotaMessage() {
    assertTrue(GeminiErrors.isRateLimit(new RuntimeException("HTTP 429 quota exceeded")));
  }

  @Test
  void ignoresUnrelatedErrors() {
    assertFalse(GeminiErrors.isRateLimit(new RuntimeException("neo4j connection refused")));
    assertFalse(GeminiErrors.isRateLimit(null));
  }

  @Test
  void constantsMatchPythonParity() {
    assertEquals(30, GeminiErrors.RATE_LIMIT_RETRY_SECONDS);
    assertEquals("llm.rate_limited", GeminiErrors.RATE_LIMIT_INTENT_ID);
    assertTrue(GeminiErrors.RATE_LIMIT_ANSWER.toLowerCase().contains("under stress"));
  }
}
