package com.sanjuthomas.policypilot.neo4j;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.cypher.CypherBuilderClient;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateResponse;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectService.Neo4jDirectResult;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class Neo4jDirectServiceTest {

  @Mock CypherBuilderClient cypherBuilderClient;
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
    when(cypherBuilderClient.plan(anyString(), eq("events"), isNull()))
        .thenReturn(
            new PlanResponse(
                true,
                "planned_graph",
                "neo4j_direct",
                List.of(
                    new PlannedQuery("count", "MATCH (e) RETURN count(e) AS total"),
                    new PlannedQuery("details", "MATCH (e) RETURN e")),
                Map.of()));
    when(cypherBuilderClient.validate(anyString()))
        .thenReturn(new ValidateResponse(true, "MATCH (e) RETURN count(e) AS total LIMIT 1", null));
    when(neo4jQueryExecutor.runRead(anyString())).thenReturn(List.of(Map.of("total", 3L)));

    Neo4jDirectService service =
        new Neo4jDirectService(cypherBuilderClient, neo4jQueryExecutor, formatter);
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
    when(cypherBuilderClient.plan(anyString(), anyString(), any()))
        .thenReturn(new PlanResponse(false, null, null, List.of(), Map.of()));
    Neo4jDirectService service =
        new Neo4jDirectService(cypherBuilderClient, neo4jQueryExecutor, formatter);
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
    when(cypherBuilderClient.plan(anyString(), eq("payments"), isNull()))
        .thenReturn(
            new PlanResponse(
                true,
                "payment.status_by_id",
                "neo4j_direct",
                List.of(new PlannedQuery("payment_detail", "MATCH (p) RETURN p")),
                Map.of()));
    when(cypherBuilderClient.validate(anyString()))
        .thenReturn(new ValidateResponse(true, "MATCH (p) RETURN p LIMIT 1", null));
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
        new Neo4jDirectService(cypherBuilderClient, neo4jQueryExecutor, formatter);
    Neo4jDirectResult result =
        service.answer(
            "What is the status of payment 20260720-FICC-P-1?", "payments", complianceSubject());

    assertEquals("Payment 20260720-FICC-P-1 has status APPROVED (LOB FICC).", result.answer());
    assertEquals("payment.status_by_id", result.intentId());
    assertEquals("predefined_yaml", result.cypherProvenance());
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
