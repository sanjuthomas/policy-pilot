package com.sanjuthomas.policypilot.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import org.junit.jupiter.api.Test;

class RouteClampsTest {

  @Test
  void clampsPastWhoApprovedFromEligibility() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");

    RouterDecision clamped =
        RouteClamps.apply(decision, "Who approved 20260720-FICC-P-19?");

    assertEquals("neo4j_direct", clamped.getPath());
    assertTrue(clamped.getReasoning().contains("clamped neo4j_direct"));
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
