package com.sanjuthomas.policypilot.extraction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
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
  void enrichesByIdStatusAndCreatorShapes() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    EntityApiQuestion.enrichDecision(
        decision, "What is the status of payment 20260720-FICC-P-1?");
    assertEquals("status", decision.getExtractionFacet());

    RouterDecision creator = new RouterDecision();
    EntityApiQuestion.enrichDecision(creator, "Who created payment 20260720-FICC-P-1?");
    assertEquals("creator", creator.getExtractionFacet());

    RouterDecision combo = new RouterDecision();
    EntityApiQuestion.enrichDecision(
        combo, "Who created payment 20260720-FICC-P-1 and who approved it?");
    assertEquals("creator_and_approver", combo.getExtractionFacet());

    RouterDecision approver = new RouterDecision();
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
