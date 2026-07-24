package com.sanjuthomas.policypilot.cypher;

import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.ValidateResult;
import com.sanjuthomas.policypilot.neo4j.GraphAnswerHints;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.time.GraphTimeWindow;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * In-process deterministic Cypher planner for Java neo4j_direct (alerts + SoD + timeline).
 *
 * <p>Plan selection comes from Spring AI {@link RouterDecision} slots ({@code graphIntent} +
 * time/scope/kind), not phrase regex. Stable tokens (instruction sequence ids) remain for timeline
 * binding. Entity inventory/detail stays on domain APIs via {@code document_extraction}.
 */
@Service
public class GraphCypherPlanner {

  public PlanResponse plan(String question, String mode) {
    return plan(question, mode, null, null);
  }

  public PlanResponse plan(String question, String mode, Set<String> allowedLobs) {
    return plan(question, mode, allowedLobs, null);
  }

  /**
   * @param allowedLobs {@code null} = unscoped (compliance); empty = deny; non-empty = FO/MO scope
   * @param decision router slots; {@code graphIntent} required for a match
   */
  public PlanResponse plan(
      String question, String mode, Set<String> allowedLobs, RouterDecision decision) {
    String resolvedMode =
        mode == null || mode.isBlank() ? "events" : mode.strip().toLowerCase(Locale.ROOT);
    String q = question == null ? "" : question;
    String intent = normalizeGraphIntent(decision == null ? null : decision.getGraphIntent());
    if (intent == null) {
      return PlanResponse.unmatched();
    }

    GraphAnswerHints hints = GraphAnswerHints.from(decision);
    String timeFilter = timeFilter(hints.timeWindow());
    String domain = domain(hints.eventScope());

    return switch (intent) {
      case "cross_entity_reciprocal_approval" ->
          modeAllows(resolvedMode, "instructions", "payments", "events", "all")
              ? matched(
                  "instruction.cross_entity_reciprocal_approval",
                  GraphCypherQueries.crossEntityReciprocalApproval())
              : PlanResponse.unmatched();
      case "mutual_approval" ->
          modeAllows(resolvedMode, "instructions", "all")
              ? matched("instruction.mutual_approval", GraphCypherQueries.mutualApproval())
              : PlanResponse.unmatched();
      case "self_approval" ->
          modeAllows(resolvedMode, "instructions", "all")
              ? matched("instruction.self_approval", GraphCypherQueries.selfApproval())
              : PlanResponse.unmatched();
      case "subordinate_approver" ->
          modeAllows(resolvedMode, "instructions", "all")
              ? matched(
                  "instruction.subordinate_approver", GraphCypherQueries.subordinateApprover())
              : PlanResponse.unmatched();
      case "duplicate_routes" ->
          modeAllows(resolvedMode, "instructions", "all")
              ? matched(
                  "instruction.duplicate_routes",
                  GraphCypherQueries.duplicateRoutes(q, allowedLobs))
              : PlanResponse.unmatched();
      case "instruction_timeline" ->
          modeAllows(resolvedMode, "events", "all")
              ? InstructionIdParser.extract(q)
                  .map(
                      id ->
                          matched(
                              "events.instruction_timeline_by_id",
                              GraphCypherQueries.instructionTimeline(id)))
                  .orElse(PlanResponse.unmatched())
              : PlanResponse.unmatched();
      case "alert_ranking" ->
          "events".equals(resolvedMode)
              ? matched(
                  "planned_graph",
                  GraphCypherQueries.alertRanking(timeFilter, domain, q, allowedLobs))
              : PlanResponse.unmatched();
      case "alert_list" ->
          modeAllows(resolvedMode, "events", "all", "instructions", "payments")
              ? matched(
                  "planned_graph",
                  GraphCypherQueries.alertList(
                      timeFilter, domain, hints.approvalDenialList(), q, allowedLobs))
              : PlanResponse.unmatched();
      case "alert_count" ->
          modeAllows(resolvedMode, "events", "all")
              ? matched(
                  "planned_graph",
                  GraphCypherQueries.alertCount(timeFilter, domain, q, allowedLobs))
              : PlanResponse.unmatched();
      default -> PlanResponse.unmatched();
    };
  }

  public ValidateResult validate(String cypher) {
    return ReadOnlyCypherValidator.validate(cypher);
  }

  static String normalizeGraphIntent(String raw) {
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    String key = raw.strip().toLowerCase(Locale.ROOT).replace('-', '_');
    return switch (key) {
      case "alert_count", "count" -> "alert_count";
      case "alert_list", "list" -> "alert_list";
      case "alert_ranking", "ranking" -> "alert_ranking";
      case "self_approval" -> "self_approval";
      case "mutual_approval" -> "mutual_approval";
      case "subordinate_approver" -> "subordinate_approver";
      case "duplicate_routes" -> "duplicate_routes";
      case "cross_entity_reciprocal_approval", "cross_entity" ->
          "cross_entity_reciprocal_approval";
      case "instruction_timeline", "timeline" -> "instruction_timeline";
      default -> null;
    };
  }

  static String timeFilter(String window) {
    return GraphTimeWindow.cypherTimestampFilter(window);
  }

  static String domain(String eventScope) {
    if ("payment".equals(eventScope)) {
      return "payments";
    }
    if ("instruction".equals(eventScope)) {
      return "instructions";
    }
    return "all";
  }

  private static PlanResponse matched(String intentId, List<PlannedQuery> planned) {
    List<PlannedQuery> normalized = new ArrayList<>();
    List<String> labels = new ArrayList<>();
    for (PlannedQuery query : planned) {
      normalized.add(
          new PlannedQuery(query.label(), ReadOnlyCypherValidator.normalize(query.cypher())));
      labels.add(query.label());
    }
    Map<String, Object> meta = new LinkedHashMap<>();
    meta.put("cypher_class", "deterministic");
    meta.put("plan_labels", labels);
    return PlanResponse.matched(intentId, normalized, meta);
  }

  private static boolean modeAllows(String mode, String... allowed) {
    for (String candidate : allowed) {
      if (candidate.equals(mode)) {
        return true;
      }
    }
    return false;
  }
}
