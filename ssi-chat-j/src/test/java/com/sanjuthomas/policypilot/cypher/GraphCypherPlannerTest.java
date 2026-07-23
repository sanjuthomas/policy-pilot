package com.sanjuthomas.policypilot.cypher;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.ValidateResult;
import java.util.Set;
import org.junit.jupiter.api.Test;

class GraphCypherPlannerTest {

  private final GraphCypherPlanner planner = new GraphCypherPlanner();

  @Test
  void plansAlertCountToday() {
    PlanResponse plan =
        planner.plan("How many ALERT events happened today?", "events", null);
    assertTrue(plan.matched());
    assertEquals("planned_graph", plan.intentId());
    assertEquals("count", plan.planned().get(0).label());
    assertTrue(plan.planned().get(0).cypher().contains("severity: 'ALERT'"));
    assertTrue(plan.planned().get(0).cypher().contains("date()"));
  }

  @Test
  void plansInstructionDenialCountWithLobScope() {
    PlanResponse plan =
        planner.plan(
            "How many instruction policy denials happened this week?",
            "events",
            Set.of("FICC"));
    assertTrue(plan.matched());
    assertTrue(plan.planned().get(0).cypher().contains("e.payment_id IS NULL"));
    assertTrue(plan.planned().get(0).cypher().contains("owning_lob = 'FICC'"));
  }

  @Test
  void plansAlertListAndRanking() {
    PlanResponse list = planner.plan("Can you report all ALERTS today?", "events", null);
    assertTrue(list.matched());
    assertEquals("security_event_alert_list", list.planned().get(0).label());

    PlanResponse ranking =
        planner.plan(
            "Which user triggered the most policy denial alerts this week?", "events", null);
    assertTrue(ranking.matched());
    assertEquals("ranking", ranking.planned().get(0).label());
  }

  @Test
  void plansSodIntents() {
    assertEquals(
        "instruction.self_approval",
        planner.plan("Show self-approved instructions", "instructions", null).intentId());
    assertEquals(
        "instruction.mutual_approval",
        planner.plan("Which users mutually approved each other?", "instructions", null)
            .intentId());
    assertEquals(
        "instruction.subordinate_approver",
        planner
            .plan(
                "Which instructions were approved by someone who reports to the creator?",
                "instructions",
                null)
            .intentId());
    assertEquals(
        "instruction.duplicate_routes",
        planner.plan("List duplicate settlement routes", "instructions", null).intentId());
    assertEquals(
        "instruction.cross_entity_reciprocal_approval",
        planner
            .plan(
                "Find cross-entity reciprocal approval between instruction and payment",
                "all",
                null)
            .intentId());
  }

  @Test
  void plansTimelineWhenInstructionIdPresent() {
    PlanResponse plan =
        planner.plan(
            "Show the security event timeline for instruction 20260720-FICC-I-1",
            "events",
            null);
    assertTrue(plan.matched());
    assertEquals("events.instruction_timeline_by_id", plan.intentId());
    assertTrue(plan.planned().get(0).cypher().contains("20260720-FICC-I-1"));
  }

  @Test
  void unmatchedForUnrelatedQuestion() {
    assertFalse(planner.plan("hello there", "events", null).matched());
  }

  @Test
  void validateRejectsWrites() {
    ValidateResult result =
        planner.validate("MATCH (n) CREATE (m:X) RETURN n LIMIT 1");
    assertFalse(result.ok());
    assertTrue(result.error().contains("write keyword"));
  }

  @Test
  void emptyAllowedLobsDenyAll() {
    PlanResponse plan =
        planner.plan("How many ALERT events happened today?", "events", Set.of());
    assertTrue(plan.matched());
    assertTrue(plan.planned().get(0).cypher().contains("AND false"));
  }
}
