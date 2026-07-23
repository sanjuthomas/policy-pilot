package com.sanjuthomas.policypilot.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import org.junit.jupiter.api.Test;

class RouteClampsTest {

  @Test
  void clampsPastWhoApprovedFromEligibilityToDocumentExtraction() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Who approved 20260720-FICC-P-19?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("approver", clamped.getExtractionFacet());
    assertTrue(clamped.getReasoning().contains("entity API"));
  }

  @Test
  void leavesWhoCanApproveOnEligibility() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");

    RouterDecision result =
        RouteClamps.apply(decision, "Who can approve 20260720-FICC-P-8?");

    assertEquals("eligibility", result.getPath());
  }

  @Test
  void detectsPastWhoApprovedAudit() {
    assertTrue(RouteClamps.isPastWhoApprovedAudit("Who approved payment 20260720-FICC-P-1?"));
    assertTrue(RouteClamps.isPastWhoApprovedAudit("Who approved 20260720-FICC-P-19?"));
    assertFalse(RouteClamps.isPastWhoApprovedAudit("Who can approve 20260720-FICC-P-8?"));
    assertFalse(
        RouteClamps.isPastWhoApprovedAudit(
            "Who created payment 20260720-FICC-P-1 and who approved it?"));
  }

  @Test
  void clampsEntityApiStatusFromNeo4jToDocumentExtraction() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setExtractionFacet("status");

    RouterDecision clamped =
        RouteClamps.apply(decision, "What is the status of payment 20260720-FICC-P-1?");

    assertEquals("document_extraction", clamped.getPath());
    assertTrue(clamped.getReasoning().contains("entity API"));
  }

  @Test
  void clampsInventoryWhenRouterFilledSlotsButChoseNeo4j() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setExtractionFacet("list_by_status");
    decision.setEntityStatus("APPROVED");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Can you list all approved instructions?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("instruction", clamped.getExtractionTarget());
  }

  @Test
  void clampsCreatorAndApproverToDocumentExtractionNotNeo4j() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setExtractionFacet("creator_and_approver");

    RouterDecision clamped =
        RouteClamps.apply(
            decision, "Who created payment 20260720-FICC-P-1 and who approved it?");

    assertEquals("document_extraction", clamped.getPath());
  }

  @Test
  void clampsCreatorAndApproverFromEligibilityToDocumentExtraction() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setExtractionFacet("creator_and_approver");

    RouterDecision result =
        RouteClamps.apply(
            decision, "Who created payment 20260720-FICC-P-1 and who approved it?");

    assertEquals("document_extraction", result.getPath());
  }

  @Test
  void clampsStatusFromNeo4jWithoutExplicitFacetSlot() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");

    RouterDecision clamped =
        RouteClamps.apply(decision, "What is the status of payment 20260720-FICC-P-1?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("status", clamped.getExtractionFacet());
  }

  @Test
  void clampsPersonPermissionsFromMePath() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("my_permissions");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Can you list the permissions of Kowalski, Anna?");

    assertEquals("person_permissions", clamped.getPath());
    assertEquals("Kowalski, Anna", clamped.getPersonQuery());
  }

  @Test
  void clampsInventoryFromLiteralApprovedWithoutFacetSlot() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Can you list all approved instructions?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("list_by_status", clamped.getExtractionFacet());
    assertEquals("APPROVED", clamped.getEntityStatus());
    assertEquals("instruction", clamped.getExtractionTarget());
  }

  @Test
  void clampsOpenNarrativeFromNeo4jDirectToVector() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");

    RouterDecision clamped =
        RouteClamps.apply(
            decision,
            "Write a brief narrative about recent policy denial activity in the audit log.");

    assertEquals("vector", clamped.getPath());
    assertTrue(clamped.getReasoning().contains("forced vector for open narrative"));
  }

  @Test
  void leavesOpenNarrativeAlreadyOnVector() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("vector");

    RouterDecision result =
        RouteClamps.apply(
            decision,
            "Write a brief narrative about recent policy denial activity in the audit log.");

    assertEquals("vector", result.getPath());
  }

  @Test
  void detectsOpenNarrativeQuestion() {
    assertTrue(
        RouteClamps.isOpenNarrativeQuestion(
            "Write a brief narrative about recent policy denial activity in the audit log."));
    assertFalse(
        RouteClamps.isOpenNarrativeQuestion("How many instruction policy denials happened this week?"));
    assertFalse(
        RouteClamps.isOpenNarrativeQuestion(
            "Write a brief narrative about payment 20260720-FICC-P-1"));
  }
}
