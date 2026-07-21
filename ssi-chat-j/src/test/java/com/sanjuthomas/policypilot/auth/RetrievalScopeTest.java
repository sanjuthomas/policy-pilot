package com.sanjuthomas.policypilot.auth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Test;

class RetrievalScopeTest {

  @Test
  void complianceIsUnscoped() {
    Subject subject =
        new Subject(
            "comp-001",
            "C",
            "One",
            "Analyst",
            "FICC",
            List.of("COMPLIANCE_ANALYST"),
            List.of(),
            null,
            List.of(),
            "t",
            "s");
    assertNull(RetrievalScope.allowedRetrievalLobs(subject));
  }

  @Test
  void foUsesDeskLob() {
    Subject subject =
        new Subject(
            "fo-fx-101",
            "F",
            "O",
            "Trader",
            "FX",
            List.of("PAYMENT_CREATOR"),
            List.of("FRONT_OFFICE"),
            null,
            List.of(),
            "t",
            "s");
    assertEquals(Set.of("FX"), RetrievalScope.allowedRetrievalLobs(subject));
  }

  @Test
  void middleOfficeUsesCoveringLobs() {
    Subject subject =
        new Subject(
            "pay-101",
            "P",
            "One",
            "MO",
            "FICC",
            List.of("FUNDING_APPROVER"),
            List.of("MIDDLE_OFFICE"),
            null,
            List.of("FX", "FICC"),
            "t",
            "s");
    Set<String> allowed = RetrievalScope.allowedRetrievalLobs(subject);
    assertTrue(allowed.contains("FX"));
    assertTrue(allowed.contains("FICC"));
  }
}
