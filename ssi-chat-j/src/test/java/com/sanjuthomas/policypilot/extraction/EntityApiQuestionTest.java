package com.sanjuthomas.policypilot.extraction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.extraction.EntityApiQuestion.Facet;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import org.junit.jupiter.api.Test;

class EntityApiQuestionTest {

  @Test
  void facetsComeFromRouterSlots() {
    RouterDecision status = new RouterDecision();
    status.setExtractionFacet("status");
    assertEquals(
        Facet.STATUS, EntityApiQuestion.resolveFacet("What is the status of payment X?", status));
    assertTrue(EntityApiQuestion.isEntityApiQuestion(status, "What is the status of payment X?"));
  }

  @Test
  void doesNotPhraseInferByIdFacetsWithoutLlmSlots() {
    RouterDecision status = new RouterDecision();
    EntityApiQuestion.enrichDecision(
        status, "What is the status of payment 20260720-FICC-P-1?");
    assertNull(status.getExtractionFacet());

    RouterDecision creator = new RouterDecision();
    EntityApiQuestion.enrichDecision(creator, "Who created payment 20260720-FICC-P-1?");
    assertNull(creator.getExtractionFacet());

    RouterDecision approver = new RouterDecision();
    EntityApiQuestion.enrichDecision(
        approver, "Who approved payment 20260720-FICC-P-1 and why?");
    assertNull(approver.getExtractionFacet());
    assertNull(approver.getEntityStatus());
  }

  @Test
  void preservesLlmFacetSlots() {
    RouterDecision approver = new RouterDecision();
    approver.setExtractionFacet("approver");
    EntityApiQuestion.enrichDecision(
        approver, "Who approved payment 20260720-FICC-P-1 and why?");
    assertEquals("approver", approver.getExtractionFacet());
    assertTrue(
        EntityApiQuestion.isEntityApiQuestion(
            approver, "Who approved payment 20260720-FICC-P-1 and why?"));
  }

  @Test
  void enrichesInventoryFromLiteralEnums() {
    RouterDecision list = new RouterDecision();
    EntityApiQuestion.enrichDecision(list, "Can you list all approved instructions?");
    assertEquals("APPROVED", list.getEntityStatus());
    assertEquals("list_by_status", list.getExtractionFacet());

    RouterDecision standing = new RouterDecision();
    EntityApiQuestion.enrichDecision(
        standing, "Can you show me the standing instructions in the system?");
    assertEquals("STANDING", standing.getInstructionType());
    assertEquals("list_standing", standing.getExtractionFacet());

    RouterDecision single = new RouterDecision();
    EntityApiQuestion.enrichDecision(single, "Can you list the single-use instructions?");
    assertEquals("SINGLE_USE", single.getInstructionType());
    assertEquals("list_single_use", single.getExtractionFacet());
  }

  @Test
  void doesNotTreatApprovedByVerbAsStatusFilter() {
    RouterDecision decision = new RouterDecision();
    EntityApiQuestion.enrichDecision(
        decision,
        "Are there any instructions approved by someone who directly reports to the creator?");
    assertNull(decision.getEntityStatus());
    assertNull(decision.getExtractionFacet());
  }

  @Test
  void doesNotTreatMutualApprovedVerbAsStatusFilter() {
    RouterDecision decision = new RouterDecision();
    EntityApiQuestion.enrichDecision(
        decision,
        "Are there any mutual approval cases (A approved B's instruction and B approved A's)?");
    assertNull(decision.getEntityStatus());
    assertNull(decision.getExtractionFacet());
    assertFalse(
        EntityApiQuestion.isEntityApiQuestion(
            decision,
            "Are there any mutual approval cases (A approved B's instruction and B approved A's)?"));
  }

  @Test
  void inventoryAndVersionsRequireSignals() {
    assertEquals(Facet.SHOW, EntityApiQuestion.resolveFacet("list paused instructions", null));
    assertFalse(EntityApiQuestion.isEntityApiQuestion(null, "list paused instructions"));
  }

  @Test
  void statusAndTypeComeFromRouterSlotsNotLemmas() {
    RouterDecision decision = new RouterDecision();
    decision.setEntityStatus("SUSPENDED");
    decision.setInstructionType("STANDING");
    decision.setExtractionFacet("list_by_status");

    assertEquals(
        "SUSPENDED", EntityApiQuestion.resolveEntityStatus("list paused instructions", decision));
    assertEquals("STANDING", EntityApiQuestion.resolveInstructionType("list evergreen", decision));
    assertEquals(
        null, EntityApiQuestion.resolveEntityStatus("list paused instructions", new RouterDecision()));
    assertEquals("APPROVED", EntityApiQuestion.resolveEntityStatus("list APPROVED instructions", null));
  }
}
