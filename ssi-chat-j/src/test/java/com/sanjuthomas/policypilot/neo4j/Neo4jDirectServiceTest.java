package com.sanjuthomas.policypilot.neo4j;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.cypher.GraphCypherPlanner;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.ValidateResult;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectService.Neo4jDirectResult;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class Neo4jDirectServiceTest {

  @Mock GraphCypherPlanner graphCypherPlanner;
  @Mock Neo4jQueryExecutor neo4jQueryExecutor;

  private Neo4jDirectAnswerFormatter formatter;

  @BeforeEach
  void setUp() {
    PolicyBasisFormat basis = new PolicyBasisFormat();
    formatter =
        new Neo4jDirectAnswerFormatter(
            new AnswerRenderer(
                new AnswerTemplateConfig().answerTemplateEngine(),
                new MoneyFormat(),
                basis),
            basis);
  }

  @Test
  void plansValidatesExecutesAndFormats() {
    when(graphCypherPlanner.plan(anyString(), eq("events"), isNull(), any()))
        .thenReturn(
            new PlanResponse(
                true,
                "planned_graph",
                "neo4j_direct",
                List.of(
                    new PlannedQuery("count", "MATCH (e) RETURN count(e) AS total"),
                    new PlannedQuery("details", "MATCH (e) RETURN e")),
                Map.of()));
    when(graphCypherPlanner.validate(anyString()))
        .thenReturn(ValidateResult.ok("MATCH (e) RETURN count(e) AS total LIMIT 1"));
    when(neo4jQueryExecutor.runRead(anyString())).thenReturn(List.of(Map.of("total", 3L)));

    Neo4jDirectService service =
        new Neo4jDirectService(graphCypherPlanner, neo4jQueryExecutor, formatter);
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setGraphTimeWindow("today");
    decision.setGraphEventKind("alert");
    Neo4jDirectResult result =
        service.answer(
            "How many ALERT events happened today?", "events", complianceSubject(), decision);

    assertEquals("There were 3 ALERT events today.", result.answer());
    assertEquals("planned_graph", result.intentId());
    assertEquals("predefined_planned", result.cypherProvenance());
    assertEquals(1, result.graphRows().size());
  }

  @Test
  void unmatchedWhenPlannerMisses() {
    when(graphCypherPlanner.plan(anyString(), anyString(), any(), any()))
        .thenReturn(PlanResponse.unmatched());
    Neo4jDirectService service =
        new Neo4jDirectService(graphCypherPlanner, neo4jQueryExecutor, formatter);
    Neo4jDirectResult result = service.answer("hello", "events", complianceSubject());
    assertNull(result.intentId());
    assertEquals("none", result.cypherProvenance());
  }

  @Test
  void selectQueryPrefersDetailThenListThenRankingThenCount() {
    PlannedQuery count = new PlannedQuery("count", "c");
    PlannedQuery details = new PlannedQuery("details", "d");
    PlannedQuery list = new PlannedQuery("security_event_alert_list", "l");
    PlannedQuery ranking = new PlannedQuery("ranking", "r");
    PlannedQuery paymentDetail = new PlannedQuery("payment_detail", "p");
    PlannedQuery inventory = new PlannedQuery("instruction_inventory", "inv");
    assertEquals(
        paymentDetail, Neo4jDirectService.selectQuery(List.of(details, count, paymentDetail)));
    assertEquals(inventory, Neo4jDirectService.selectQuery(List.of(details, count, inventory)));
    assertEquals(list, Neo4jDirectService.selectQuery(List.of(details, count, list)));
    assertEquals(ranking, Neo4jDirectService.selectQuery(List.of(details, ranking, count)));
    assertEquals(count, Neo4jDirectService.selectQuery(List.of(details, count)));
  }

  @Test
  void formatsPaymentStatusViaEntityIntent() {
    when(graphCypherPlanner.plan(anyString(), eq("payments"), isNull(), any()))
        .thenReturn(
            new PlanResponse(
                true,
                "payment.status_by_id",
                "neo4j_direct",
                List.of(new PlannedQuery("payment_detail", "MATCH (p) RETURN p")),
                Map.of()));
    when(graphCypherPlanner.validate(anyString()))
        .thenReturn(ValidateResult.ok("MATCH (p) RETURN p LIMIT 1"));
    when(neo4jQueryExecutor.runRead(anyString()))
        .thenReturn(
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-1",
                    "status",
                    "APPROVED",
                    "owning_lob",
                    "FICC")));

    Neo4jDirectService service =
        new Neo4jDirectService(graphCypherPlanner, neo4jQueryExecutor, formatter);
    Neo4jDirectResult result =
        service.answer(
            "What is the status of payment 20260720-FICC-P-1?", "payments", complianceSubject());

    assertEquals("Payment 20260720-FICC-P-1 has status APPROVED (LOB FICC).", result.answer());
    assertEquals("payment.status_by_id", result.intentId());
    assertEquals("predefined_yaml", result.cypherProvenance());
  }

  @Test
  void filterRowsByRetrievalLobsFailsClosedWithoutRecognizableLob() {
    List<Map<String, Object>> rows =
        List.of(
            Map.of("instruction_id", "FX-1", "v.owning_lob", "FX"),
            Map.of("instruction_id", "FICC-1", "owning_lob", "FICC"),
            Map.of("instruction_id", "NOLOB", "status", "APPROVED"));

    List<Map<String, Object>> kept =
        Neo4jDirectService.filterRowsByRetrievalLobs(rows, Set.of("FICC"));

    assertEquals(1, kept.size());
    assertEquals("FICC-1", kept.get(0).get("instruction_id"));
  }

  @Test
  void filterRowsByRetrievalLobsRequiresAllLobsInScopeForMutualShape() {
    List<Map<String, Object>> rows =
        List.of(
            Map.of("lob_a", "FICC", "lob_b", "FICC", "user_a_id", "a"),
            Map.of("lob_a", "FICC", "lob_b", "FX", "user_a_id", "b"));

    List<Map<String, Object>> kept =
        Neo4jDirectService.filterRowsByRetrievalLobs(rows, Set.of("FICC"));

    assertEquals(1, kept.size());
    assertEquals("a", kept.get(0).get("user_a_id"));
  }

  @Test
  void filterRowsByRetrievalLobsDropsCrossLobDuplicateRoutes() {
    List<Map<String, Object>> rows =
        List.of(
            Map.of(
                "instruction_id_a",
                "FICC-1",
                "instruction_id_b",
                "FICC-2",
                "owning_lob",
                "FICC",
                "lob_b",
                "FICC"),
            Map.of(
                "instruction_id_a",
                "FICC-3",
                "instruction_id_b",
                "FX-9",
                "owning_lob",
                "FICC",
                "lob_b",
                "FX"));

    List<Map<String, Object>> kept =
        Neo4jDirectService.filterRowsByRetrievalLobs(rows, Set.of("FICC"));

    assertEquals(1, kept.size());
    assertEquals("FICC-1", kept.get(0).get("instruction_id_a"));
  }

  @Test
  void filterRowsByRetrievalLobsUnscopedKeepsAll() {
    List<Map<String, Object>> rows =
        List.of(Map.of("instruction_id", "X"), Map.of("owning_lob", "FX"));
    assertEquals(2, Neo4jDirectService.filterRowsByRetrievalLobs(rows, null).size());
  }

  @Test
  void filterRowsByRetrievalLobsEmptyScopeDropsAll() {
    List<Map<String, Object>> rows = List.of(Map.of("owning_lob", "FICC"));
    assertEquals(0, Neo4jDirectService.filterRowsByRetrievalLobs(rows, Set.of()).size());
  }

  @Test
  void filterKeepsCypherScopedAggregatesWithoutLobColumn() {
    List<Map<String, Object>> countRows = List.of(Map.of("total", 6L));
    assertEquals(
        1,
        Neo4jDirectService.filterRowsByRetrievalLobs(countRows, Set.of("FICC"), "count").size());
    assertEquals(
        0, Neo4jDirectService.filterRowsByRetrievalLobs(countRows, Set.of("FICC"), null).size());

    List<Map<String, Object>> rankingRows =
        List.of(Map.of("user_id", "u1", "alert_count", 3L));
    assertEquals(
        1,
        Neo4jDirectService.filterRowsByRetrievalLobs(rankingRows, Set.of("FICC"), "ranking")
            .size());
  }

  @Test
  void filterStillFailsClosedForAlertListWithoutLob() {
    List<Map<String, Object>> listRows =
        List.of(Map.of("event_id", "e1", "action", "APPROVE"));
    assertEquals(
        0,
        Neo4jDirectService.filterRowsByRetrievalLobs(
                listRows, Set.of("FICC"), "security_event_alert_list")
            .size());
    assertEquals(
        1,
        Neo4jDirectService.filterRowsByRetrievalLobs(
                List.of(Map.of("event_id", "e1", "owning_lob", "FICC")),
                Set.of("FICC"),
                "security_event_alert_list")
            .size());
  }

  @Test
  void rowOwningLobsReadsAlternateKeysAndNullSafe() {
    assertEquals(Set.of(), Neo4jDirectService.rowOwningLobs(null));
    assertEquals(
        Set.of("FX"),
        Neo4jDirectService.rowOwningLobs(Map.of("instruction_owning_lob", "fx", "status", "X")));
    assertEquals(Set.of("FICC"), Neo4jDirectService.rowOwningLobs(Map.of("lob", "FICC")));
  }

  private static Subject complianceSubject() {
    return new Subject(
        "comp-001",
        "Comp",
        "One",
        "Analyst",
        "FICC",
        List.of("COMPLIANCE_ANALYST"),
        List.of(),
        null,
        List.of(),
        "tok",
        "sess");
  }
}
