package com.policypilot.chatj.pipeline;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

class RouterDecisionTest {

  @Test
  void gettersAndSettersRoundTrip() {
    RouterDecision d = new RouterDecision();
    d.setPath("eligibility");
    d.setEligibilityTarget("payment");
    d.setEligibilityAction("APPROVE");
    d.setReasoning("because");
    assertEquals("eligibility", d.getPath());
    assertEquals("payment", d.getEligibilityTarget());
    assertEquals("APPROVE", d.getEligibilityAction());
    assertEquals("because", d.getReasoning());
    d.setReasoning(null);
    assertEquals("", d.getReasoning());
    assertNull(new RouterDecision().getPath());
  }

  @Test
  void directoryAmountSlotsRoundTrip() {
    RouterDecision d = new RouterDecision();
    d.setPath("policy_directory");
    d.setDirectoryAmount(1_000_000_000.0);
    d.setDirectoryAmountStrict(false);
    d.setDirectoryCoveringLob("FICC");
    assertEquals(1_000_000_000.0, d.getDirectoryAmount());
    assertEquals(false, d.getDirectoryAmountStrict());
    assertEquals("FICC", d.getDirectoryCoveringLob());
  }
}
