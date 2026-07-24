package com.sanjuthomas.policypilot.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import org.junit.jupiter.api.Test;

class RouteClampsTest {

  @Test
  void clampsWhenLlmSetApproverFacetButChoseEligibility() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    decision.setExtractionFacet("approver");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Who approved 20260720-FICC-P-19?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("approver", clamped.getExtractionFacet());
    assertTrue(clamped.getReasoning().contains("entity API"));
  }

  @Test
  void leavesWhoCanApproveOnEligibilityWithoutEntityApiSlots() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");

    RouterDecision result =
        RouteClamps.apply(decision, "Who can approve 20260720-FICC-P-8?");

    assertEquals("eligibility", result.getPath());
  }

  @Test
  void doesNotPhraseForceWhoApprovedOntoDocumentExtraction() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");

    RouterDecision result =
        RouteClamps.apply(decision, "Who approved 20260720-FICC-P-19?");

    assertEquals("eligibility", result.getPath());
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
  void leavesOpenNarrativePathToLlmNoPhraseClamp() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");

    RouterDecision result =
        RouteClamps.apply(
            decision,
            "Write a brief narrative about recent policy denial activity in the audit log.");

    assertEquals("neo4j_direct", result.getPath());
  }

  @Test
  void leavesGraphSodPathToLlmNoPhraseClamp() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");

    RouterDecision result =
        RouteClamps.apply(
            decision,
            "Are there any instructions approved by someone who directly reports to the creator?");

    // No phrase SoD rewrite — router must choose neo4j_direct.
    assertEquals("document_extraction", result.getPath());
  }

  @Test
  void doesNotStealMutualApprovalOntoInventoryFromApprovedVerb() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");

    RouterDecision result =
        RouteClamps.apply(
            decision,
            "Are there any mutual approval cases (A approved B's instruction and B approved A's)?");

    assertEquals("neo4j_direct", result.getPath());
  }

  @Test
  void clampsPersonPermissionsWhenLlmSetPersonQueryOnMePath() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("my_permissions");
    decision.setPersonQuery("Kowalski, Anna");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Can you list the permissions of Kowalski, Anna?");

    assertEquals("person_permissions", clamped.getPath());
    assertEquals("Kowalski, Anna", clamped.getPersonQuery());
    assertTrue(clamped.getReasoning().contains("personQuery slot"));
  }

  @Test
  void doesNotPhraseExtractPersonQueryOntoPersonPermissions() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("my_permissions");

    RouterDecision result =
        RouteClamps.apply(decision, "Can you list the permissions of Kowalski, Anna?");

    assertEquals("me", result.getPath());
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
  void doesNotPhraseStealVersionsOrCreatedByOntoDocumentExtraction() {
    RouterDecision versions = new RouterDecision();
    versions.setPath("neo4j_direct");
    assertEquals(
        "neo4j_direct",
        RouteClamps.apply(versions, "List all versions of instruction 20260720-FICC-I-1")
            .getPath());

    RouterDecision createdBy = new RouterDecision();
    createdBy.setPath("neo4j_direct");
    assertEquals(
        "neo4j_direct",
        RouteClamps.apply(createdBy, "Which instructions were created by mo-050?").getPath());
  }

  @Test
  void clampsVersionsWhenLlmSetFacetOnWrongPath() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setExtractionFacet("versions");

    RouterDecision clamped =
        RouteClamps.apply(decision, "List all versions of instruction 20260720-FICC-I-1");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("versions", clamped.getExtractionFacet());
  }

  @Test
  void clampsCreatedByUserWhenLlmSetFacetOnWrongPath() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setExtractionFacet("created_by_user");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Which instructions were created by mo-050?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("created_by_user", clamped.getExtractionFacet());
    assertEquals("instruction", clamped.getExtractionTarget());
  }

  @Test
  void keepsPaymentTargetForInventoryCount() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("payment");
    decision.setExtractionFacet("count");
    decision.setEntityStatus("SUBMITTED");

    RouterDecision clamped =
        RouteClamps.apply(decision, "How many payments are in SUBMITTED status?");

    assertEquals("document_extraction", clamped.getPath());
    assertEquals("payment", clamped.getExtractionTarget());
    assertEquals("count", clamped.getExtractionFacet());
  }
}
