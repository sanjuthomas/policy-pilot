package com.sanjuthomas.policypilot.eligibility;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class HttpErrorBodiesTest {

  @Test
  void unwrapsFastapiDetailString() {
    assertEquals(
        "not authorized to view payment",
        HttpErrorBodies.detail("{\"detail\":\"not authorized to view payment\"}"));
  }

  @Test
  void returnsRawWhenNotJson() {
    assertEquals("denied", HttpErrorBodies.detail("denied"));
  }

  @Test
  void emptyBody() {
    assertEquals("", HttpErrorBodies.detail(""));
    assertEquals("", HttpErrorBodies.detail(null));
  }
}
