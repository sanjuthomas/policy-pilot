package com.sanjuthomas.policypilot.neo4j;

import com.sanjuthomas.policypilot.cypher.CypherBuilderClient;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateResponse;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;

/** neo4j_direct lane: plan via cypher-builder-svc → validate → Neo4j → formatter. */
@Service
public class Neo4jDirectService {

  private final CypherBuilderClient cypherBuilderClient;
  private final Neo4jQueryExecutor neo4jQueryExecutor;
  private final Neo4jDirectAnswerFormatter answerFormatter;

  public Neo4jDirectService(
      CypherBuilderClient cypherBuilderClient,
      Neo4jQueryExecutor neo4jQueryExecutor,
      Neo4jDirectAnswerFormatter answerFormatter) {
    this.cypherBuilderClient = cypherBuilderClient;
    this.neo4jQueryExecutor = neo4jQueryExecutor;
    this.answerFormatter = answerFormatter;
  }

  public Neo4jDirectResult answer(String question, String mode) {
    PlanResponse plan = cypherBuilderClient.plan(question, mode);
    if (!plan.matched() || plan.planned() == null || plan.planned().isEmpty()) {
      return Neo4jDirectResult.unmatched(
          "I could not match that question to a deterministic graph query yet.");
    }

    Set<String> labels = new LinkedHashSet<>();
    for (PlannedQuery query : plan.planned()) {
      if (query != null && query.label() != null) {
        labels.add(query.label());
      }
    }

    PlannedQuery selected = selectQuery(plan.planned());
    if (selected == null || selected.cypher() == null || selected.cypher().isBlank()) {
      return Neo4jDirectResult.unmatched("Planner returned an empty Cypher plan.");
    }

    ValidateResponse validated = cypherBuilderClient.validate(selected.cypher());
    if (!validated.ok() || validated.cypher() == null) {
      return Neo4jDirectResult.unmatched(
          "Planned Cypher failed read-only validation"
              + (validated.error() == null ? "." : ": " + validated.error()));
    }

    List<Map<String, Object>> rows = neo4jQueryExecutor.runRead(validated.cypher());
    String answer = answerFormatter.format(question, labels, rows);
    return new Neo4jDirectResult(
        answer,
        plan.intentId() == null ? "planned_graph" : plan.intentId(),
        validated.cypher(),
        rows,
        "predefined_planned");
  }

  /** Prefer the count query when present (skip expensive details for count answers). */
  static PlannedQuery selectQuery(List<PlannedQuery> planned) {
    for (PlannedQuery query : planned) {
      if (query != null && "count".equals(query.label())) {
        return query;
      }
    }
    for (PlannedQuery query : planned) {
      if (query != null) {
        return query;
      }
    }
    return null;
  }

  public record Neo4jDirectResult(
      String answer,
      String intentId,
      String cypher,
      List<Map<String, Object>> graphRows,
      String cypherProvenance) {

    static Neo4jDirectResult unmatched(String message) {
      return new Neo4jDirectResult(message, null, null, List.of(), "none");
    }
  }
}
