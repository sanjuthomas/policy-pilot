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
}
