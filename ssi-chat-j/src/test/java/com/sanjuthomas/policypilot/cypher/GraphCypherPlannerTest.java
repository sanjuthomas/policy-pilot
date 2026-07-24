package com.sanjuthomas.policypilot.cypher;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.ValidateResult;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Set;
import org.junit.jupiter.api.Test;

class GraphCypherPlannerTest {

  private final GraphCypherPlanner planner = new GraphCypherPlanner();

  @Test
  void plansAlertCountTodayFromSlots() {
    PlanResponse plan =
        planner.plan(
            "How many ALERT events happened today?",
            "events",
            null,
            decision("alert_count", "today", null, "alert"));
    assertTrue(plan.matched());
    assertEquals("planned_graph", plan.intentId());
    assertEquals("count", plan.planned().get(0).label());
    assertTrue(plan.planned().get(0).cypher().contains("severity: 'ALERT'"));
    assertTrue(plan.planned().get(0).cypher().contains("date()"));
  }

  @Test
  void plansAlertCountMonthQuarterYearFromSlots() {
    PlanResponse month =
        planner.plan(
            "How many ALERT events this month?",
            "events",
            null,
            decision("alert_count", "month", null, "alert"));
    assertTrue(month.matched());
    assertTrue(month.planned().get(0).cypher().contains("truncate('month'"));

    PlanResponse quarter =
        planner.plan(
            "How many ALERT events this quarter?",
            "events",
            null,
            decision("alert_count", "quarter", null, "alert"));
    assertTrue(quarter.planned().get(0).cypher().contains("truncate('quarter'"));

    PlanResponse year =
        planner.plan(
            "How many ALERT events this year?",
            "events",
            null,
            decision("alert_count", "year", null, "alert"));
    assertTrue(year.planned().get(0).cypher().contains("truncate('year'"));
  }

  @Test
  void plansInstructionDenialCountWithLobScope() {
    PlanResponse plan =
        planner.plan(
            "How many instruction policy denials happened this week?",
            "events",
            Set.of("FICC"),
            decision("alert_count", "week", "instruction", "denial"));
    assertTrue(plan.matched());
    assertTrue(plan.planned().get(0).cypher().contains("e.payment_id IS NULL"));
    assertTrue(plan.planned().get(0).cypher().contains("owning_lob = 'FICC'"));
  }

  @Test
  void plansAlertListAndRankingFromSlots() {
    PlanResponse list =
        planner.plan(
            "Can you report all ALERTS today?",
            "events",
            null,
            decision("alert_list", "today", null, "alert"));
    assertTrue(list.matched());
    assertEquals("security_event_alert_list", list.planned().get(0).label());

    PlanResponse ranking =
        planner.plan(
            "Which user triggered the most policy denial alerts this week?",
            "events",
            null,
            decision("alert_ranking", "week", null, "denial"));
    assertTrue(ranking.matched());
    assertEquals("ranking", ranking.planned().get(0).label());
  }

  @Test
  void plansSodIntentsFromSlots() {
    assertEquals(
        "instruction.self_approval",
        planner
            .plan("Show self-approved instructions", "instructions", null, decision("self_approval"))
            .intentId());
    assertEquals(
        "instruction.mutual_approval",
        planner
            .plan(
                "Which users mutually approved each other?",
                "instructions",
                null,
                decision("mutual_approval"))
            .intentId());
    assertEquals(
        "instruction.subordinate_approver",
        planner
            .plan(
                "Which instructions were approved by someone who reports to the creator?",
                "instructions",
                null,
                decision("subordinate_approver"))
            .intentId());
    assertEquals(
        "instruction.duplicate_routes",
        planner
            .plan(
                "List duplicate settlement routes",
                "instructions",
                null,
                decision("duplicate_routes"))
            .intentId());
    assertEquals(
        "instruction.cross_entity_reciprocal_approval",
        planner
            .plan(
                "Find cross-entity reciprocal approval between instruction and payment",
                "all",
                null,
                decision("cross_entity_reciprocal_approval"))
            .intentId());
  }

  @Test
  void plansTimelineWhenInstructionIdPresent() {
    PlanResponse plan =
        planner.plan(
            "Show the security event timeline for instruction 20260720-FICC-I-1",
            "events",
            null,
            decision("instruction_timeline"));
    assertTrue(plan.matched());
    assertEquals("events.instruction_timeline_by_id", plan.intentId());
    assertTrue(plan.planned().get(0).cypher().contains("20260720-FICC-I-1"));
  }

  @Test
  void unmatchedWithoutGraphIntentSlot() {
    assertFalse(planner.plan("How many ALERT events happened today?", "events", null, null).matched());
    assertFalse(
        planner
            .plan("How many ALERT events happened today?", "events", null, new RouterDecision())
            .matched());
  }

  @Test
  void validateRejectsWrites() {
    ValidateResult bad = planner.validate("MATCH (n) DELETE n RETURN n");
    assertFalse(bad.ok());
  }

  private static RouterDecision decision(String graphIntent) {
    return decision(graphIntent, null, null, null);
  }

  private static RouterDecision decision(
      String graphIntent, String window, String scope, String kind) {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setGraphIntent(graphIntent);
    decision.setGraphTimeWindow(window);
    decision.setGraphEventScope(scope);
    decision.setGraphEventKind(kind);
    return decision;
  }
}
