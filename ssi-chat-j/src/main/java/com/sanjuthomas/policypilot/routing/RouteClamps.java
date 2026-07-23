package com.sanjuthomas.policypilot.routing;

import com.sanjuthomas.policypilot.extraction.EntityApiQuestion;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Locale;
import java.util.Set;
import org.springframework.util.StringUtils;

/**
 * Deterministic <em>post-router</em> path clamps — the documented exception to “path comes from
 * Spring AI only.”
 *
 * <p>Primary intent is Spring AI structured {@code RouterDecision}. These helpers may rewrite
 * {@code path} / fill blank entity-API slots <strong>before</strong> {@code ChatPathDispatcher}.
 *
 * <p><strong>Not NLU:</strong> do not add phrase detectors here (who-approved vs who-can, open
 * narrative, SoD wordings, named-person phrase extractors). Those belong in {@code RouterPrompts}
 * + {@code RouterDecision} slots. Clamps may only use LLM slots already set or stable tokens
 * (sequence ids, literal enums).
 */
public final class RouteClamps {

  private static final Set<String> ENTITY_API_STEAL_PATHS =
      Set.of("neo4j_direct", "graph", "hybrid", "eligibility", "vector", "full_rag");

  private RouteClamps() {}

  public static RouterDecision apply(RouterDecision decision, String question) {
    if (decision == null) {
      return null;
    }
    decision = clampPersonPermissions(decision);
    return clampEntityApi(decision, question);
  }

  /**
   * When the LLM already set {@code personQuery} but chose {@code me} / {@code eligibility}, prefer
   * {@code person_permissions}. Does not phrase-extract names from the question.
   */
  private static RouterDecision clampPersonPermissions(RouterDecision decision) {
    if (!StringUtils.hasText(decision.getPersonQuery())) {
      return decision;
    }
    String path = decision.getPath() == null ? "" : decision.getPath().toLowerCase(Locale.ROOT);
    if ("person_permissions".equals(path)) {
      return decision;
    }
    if (!"me".equals(path) && !"eligibility".equals(path)) {
      return decision;
    }
    String prior = decision.getPath();
    decision.setPath("person_permissions");
    appendReasoning(decision, "clamped person_permissions (personQuery slot; was " + prior + ")");
    return decision;
  }

  /**
   * Prefer instruction/payment domain APIs when LLM slots or stable inventory tokens say so.
   * Does not phrase-match open narratives or SoD questions onto a path.
   */
  private static RouterDecision clampEntityApi(RouterDecision decision, String question) {
    EntityApiQuestion.enrichDecision(decision, question);
    if (!EntityApiQuestion.isEntityApiQuestion(decision, question)) {
      return decision;
    }
    String path = decision.getPath() == null ? "" : decision.getPath().toLowerCase(Locale.ROOT);
    if ("document_extraction".equals(path)) {
      ensureInventoryTarget(decision);
      return decision;
    }
    if (!ENTITY_API_STEAL_PATHS.contains(path)) {
      return decision;
    }
    String prior = decision.getPath();
    decision.setPath("document_extraction");
    ensureInventoryTarget(decision);
    appendReasoning(decision, "clamped document_extraction (entity API; was " + prior + ")");
    return decision;
  }

  private static void ensureInventoryTarget(RouterDecision decision) {
    if (EntityApiQuestion.isInventoryFacet(
        EntityApiQuestion.facetFromSlot(decision.getExtractionFacet()))) {
      decision.setExtractionTarget("instruction");
    }
  }

  private static void appendReasoning(RouterDecision decision, String note) {
    String reasoning = decision.getReasoning() == null ? "" : decision.getReasoning().trim();
    decision.setReasoning(reasoning.isEmpty() ? note : reasoning + "; " + note);
  }
}
