package com.sanjuthomas.policypilot.neo4j;

import com.sanjuthomas.policypilot.auth.RetrievalScope;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.cypher.CypherBuilderClient;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateResponse;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
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

  public Neo4jDirectResult answer(String question, String mode, Subject subject) {
    return answer(question, mode, subject, null);
  }

  public Neo4jDirectResult answer(
      String question, String mode, Subject subject, RouterDecision decision) {
    Set<String> allowedLobs = RetrievalScope.allowedRetrievalLobs(subject);
    PlanResponse plan = cypherBuilderClient.plan(question, mode, allowedLobs);
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

    List<Map<String, Object>> rows =
        filterRowsByRetrievalLobs(neo4jQueryExecutor.runRead(validated.cypher()), allowedLobs);
    String intentId = plan.intentId() == null ? "planned_graph" : plan.intentId();
    String answer =
        answerFormatter.format(
            question, labels, rows, intentId, GraphAnswerHints.from(decision));
    return new Neo4jDirectResult(
        answer, intentId, validated.cypher(), rows, provenanceForIntent(intentId));
  }

  /**
   * Prefer entity detail / list / ranking when present; otherwise count; else first planned query.
   */
  static PlannedQuery selectQuery(List<PlannedQuery> planned) {
    PlannedQuery byLabel = findLabel(planned, "payment_approval_lookup");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "approval_lookup");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "payment_detail");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "instruction_detail");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "instruction_inventory");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "instructions_by_creator");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "security_event_alert_list");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "ranking");
    if (byLabel != null) {
      return byLabel;
    }
    byLabel = findLabel(planned, "count");
    if (byLabel != null) {
      return byLabel;
    }
    for (PlannedQuery query : planned) {
      if (query != null) {
        return query;
      }
    }
    return null;
  }

  static String provenanceForIntent(String intentId) {
    if (intentId != null
        && (intentId.startsWith("payment.") || intentId.startsWith("instruction."))) {
      return "predefined_yaml";
    }
    return "predefined_planned";
  }

  private static PlannedQuery findLabel(List<PlannedQuery> planned, String label) {
    for (PlannedQuery query : planned) {
      if (query != null && label.equals(query.label())) {
        return query;
      }
    }
    return null;
  }

  /** Defense-in-depth row filter (parity with Python {@code filter_rows_by_retrieval_lobs}). */
  static List<Map<String, Object>> filterRowsByRetrievalLobs(
      List<Map<String, Object>> rows, Set<String> allowedLobs) {
    if (allowedLobs == null || rows == null) {
      return rows == null ? List.of() : rows;
    }
    List<Map<String, Object>> kept = new ArrayList<>();
    for (Map<String, Object> row : rows) {
      String lob = rowOwningLob(row);
      if (lob == null || allowedLobs.contains(lob)) {
        kept.add(row);
      }
    }
    return kept;
  }

  private static String rowOwningLob(Map<String, Object> row) {
    if (row == null) {
      return null;
    }
    for (String key : List.of("owning_lob", "lob", "instruction_owning_lob")) {
      Object value = row.get(key);
      if (value instanceof String text && !text.isBlank()) {
        return text.strip().toUpperCase(Locale.ROOT);
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
