package com.sanjuthomas.policypilot.pipeline;

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

  @Test
  void policySummarySlotsRoundTrip() {
    RouterDecision d = new RouterDecision();
    d.setPath("policy_summary");
    d.setPolicyDomain("instruction");
    d.setPolicyAction("APPROVE");
    assertEquals("policy_summary", d.getPath());
    assertEquals("instruction", d.getPolicyDomain());
    assertEquals("APPROVE", d.getPolicyAction());
  }

  @Test
  void personQuerySlotRoundTrip() {
    RouterDecision d = new RouterDecision();
    d.setPath("person_permissions");
    d.setPersonQuery("Kowalski, Anna");
    assertEquals("person_permissions", d.getPath());
    assertEquals("Kowalski, Anna", d.getPersonQuery());
  }

  @Test
  void documentExtractionSlotsRoundTrip() {
    RouterDecision d = new RouterDecision();
    d.setPath("document_extraction");
    d.setExtractionTarget("instruction");
    d.setExtractionFacet("list_by_status");
    d.setEntityStatus("SUSPENDED");
    d.setInstructionType("STANDING");
    assertEquals("document_extraction", d.getPath());
    assertEquals("instruction", d.getExtractionTarget());
    assertEquals("list_by_status", d.getExtractionFacet());
    assertEquals("SUSPENDED", d.getEntityStatus());
    assertEquals("STANDING", d.getInstructionType());
  }

  @Test
  void graphAnswerSlotsRoundTrip() {
    RouterDecision d = new RouterDecision();
    d.setPath("neo4j_direct");
    d.setGraphTimeWindow("week");
    d.setGraphEventScope("instruction");
    d.setGraphEventKind("denial");
    assertEquals("week", d.getGraphTimeWindow());
    assertEquals("instruction", d.getGraphEventScope());
    assertEquals("denial", d.getGraphEventKind());
  }
}
