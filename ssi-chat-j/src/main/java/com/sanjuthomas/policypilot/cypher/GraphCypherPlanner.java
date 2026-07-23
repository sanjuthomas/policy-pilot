package com.sanjuthomas.policypilot.cypher;

import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlannedQuery;
import com.sanjuthomas.policypilot.cypher.GraphPlanModels.ValidateResult;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;

/**
 * In-process deterministic Cypher planner for Java neo4j_direct (alerts + SoD + timeline).
 *
 * <p>Replaces the former HTTP bridge to {@code cypher-builder-svc}. Entity inventory/detail stays
 * on domain APIs via {@code document_extraction}.
 */
@Service
public class GraphCypherPlanner {

  public PlanResponse plan(String question, String mode) {
    return plan(question, mode, null);
  }

  /**
   * @param allowedLobs {@code null} = unscoped (compliance); empty = deny; non-empty = FO/MO scope
   */
  public PlanResponse plan(String question, String mode, Set<String> allowedLobs) {
    String resolvedMode =
        mode == null || mode.isBlank() ? "events" : mode.strip().toLowerCase(Locale.ROOT);
    String q = question == null ? "" : question;

    if (modeAllows(resolvedMode, "instructions", "payments", "events", "all")
        && GraphQuestionFlags.isCrossEntityReciprocal(q)) {
      return matched("instruction.cross_entity_reciprocal_approval", GraphCypherQueries.crossEntityReciprocalApproval());
    }
    if (modeAllows(resolvedMode, "instructions", "all") && GraphQuestionFlags.isMutualApproval(q)) {
      return matched("instruction.mutual_approval", GraphCypherQueries.mutualApproval());
    }
    if (modeAllows(resolvedMode, "instructions", "all") && GraphQuestionFlags.isSelfApproval(q)) {
      return matched("instruction.self_approval", GraphCypherQueries.selfApproval());
    }
    if (modeAllows(resolvedMode, "instructions", "all")
        && GraphQuestionFlags.isSubordinateApprover(q)) {
      return matched("instruction.subordinate_approver", GraphCypherQueries.subordinateApprover());
    }
    if (modeAllows(resolvedMode, "instructions", "all")
        && GraphQuestionFlags.isDuplicateRoutes(q)) {
      return matched(
          "instruction.duplicate_routes", GraphCypherQueries.duplicateRoutes(q, allowedLobs));
    }
    if (modeAllows(resolvedMode, "events", "all") && GraphQuestionFlags.isTimeline(q)) {
      return InstructionIdParser.extract(q)
          .map(
              id ->
                  matched(
                      "events.instruction_timeline_by_id",
                      GraphCypherQueries.instructionTimeline(id)))
          .orElse(PlanResponse.unmatched());
    }

    GraphQuestionFlags flags = GraphQuestionFlags.from(q);
    String timeFilter = flags.timeFilter();
    String domain = flags.domain();

    if ("events".equals(resolvedMode)
        && flags.ranking
        && flags.denial
        && (flags.alerts || flags.denial)) {
      String rankingDomain =
          flags.payments ? "payments" : flags.instructions ? "instructions" : "all";
      return matched(
          "planned_graph",
          GraphCypherQueries.alertRanking(timeFilter, rankingDomain, q, allowedLobs));
    }

    if (modeAllows(resolvedMode, "events", "all", "instructions", "payments")
        && GraphQuestionFlags.isAlertList(q)
        && !flags.count
        && !flags.ranking) {
      boolean approvalOnly = GraphQuestionFlags.isApprovalDenialList(q);
      return matched(
          "planned_graph",
          GraphCypherQueries.alertList(timeFilter, domain, approvalOnly, q, allowedLobs));
    }

    if (modeAllows(resolvedMode, "events", "all")
        && flags.count
        && (flags.alerts || flags.denial)) {
      return matched(
          "planned_graph", GraphCypherQueries.alertCount(timeFilter, domain, q, allowedLobs));
    }

    return PlanResponse.unmatched();
  }

  public ValidateResult validate(String cypher) {
    return ReadOnlyCypherValidator.validate(cypher);
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
