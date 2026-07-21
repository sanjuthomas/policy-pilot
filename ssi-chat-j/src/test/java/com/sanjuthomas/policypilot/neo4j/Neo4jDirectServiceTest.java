package com.sanjuthomas.policypilot.neo4j;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.cypher.CypherBuilderClient;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateResponse;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectService.Neo4jDirectResult;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class Neo4jDirectServiceTest {

  @Mock CypherBuilderClient cypherBuilderClient;
  @Mock Neo4jQueryExecutor neo4jQueryExecutor;

  @Test
  void plansValidatesExecutesAndFormats() {
    when(cypherBuilderClient.plan(anyString(), eq("events")))
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
        new Neo4jDirectService(
            cypherBuilderClient, neo4jQueryExecutor, new Neo4jDirectAnswerFormatter());
    Neo4jDirectResult result =
        service.answer("How many ALERT events happened today?", "events");

    assertEquals("There were 3 ALERT events today.", result.answer());
    assertEquals("planned_graph", result.intentId());
    assertEquals("predefined_planned", result.cypherProvenance());
    assertEquals(1, result.graphRows().size());
  }

  @Test
  void unmatchedWhenPlannerMisses() {
    when(cypherBuilderClient.plan(anyString(), anyString()))
        .thenReturn(new PlanResponse(false, null, null, List.of(), Map.of()));
    Neo4jDirectService service =
        new Neo4jDirectService(
            cypherBuilderClient, neo4jQueryExecutor, new Neo4jDirectAnswerFormatter());
    Neo4jDirectResult result = service.answer("hello", "events");
    assertNull(result.intentId());
    assertEquals("none", result.cypherProvenance());
  }

  @Test
  void selectQueryPrefersCount() {
    PlannedQuery count = new PlannedQuery("count", "c");
    PlannedQuery details = new PlannedQuery("details", "d");
    assertEquals(count, Neo4jDirectService.selectQuery(List.of(details, count)));
  }
}
