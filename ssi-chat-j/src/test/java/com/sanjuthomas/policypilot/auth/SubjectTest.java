package com.sanjuthomas.policypilot.auth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.List;
import org.junit.jupiter.api.Test;

class SubjectTest {

  @Test
  void withTokensCopiesIdentityFields() {
    Subject base =
        new Subject(
            "comp-001",
            "Comp",
            "One",
            "Analyst",
            "FICC",
            List.of("COMPLIANCE_ANALYST"),
            List.of("grp"),
            "sup-1",
            List.of("EM"),
            null,
            null);

    Subject withTokens = base.withTokens("tok", "sess");

    assertEquals("comp-001", withTokens.userId());
    assertEquals("Analyst", withTokens.title());
    assertEquals("tok", withTokens.bearerToken());
    assertEquals("sess", withTokens.sessionId());
    assertNull(base.bearerToken());
  }
}
