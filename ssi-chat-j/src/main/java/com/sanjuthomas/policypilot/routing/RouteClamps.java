package com.sanjuthomas.policypilot.routing;

import com.sanjuthomas.policypilot.extraction.EntityApiQuestion;
import com.sanjuthomas.policypilot.person.PersonQueryParser;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;
import org.springframework.util.StringUtils;

/**
 * Deterministic <em>post-router</em> path clamps — the documented exception to “path comes from
 * Spring AI only.”
 *
 * <p>Primary intent is still Spring AI structured {@code RouterDecision}. These helpers may rewrite
 * {@code path} / fill blank entity-API slots <strong>before</strong> {@code ChatPathDispatcher}.
 *
 * <ul>
 *   <li>Entity status / creator / approver / inventory / versions (domain API) → {@code
 *       document_extraction}; blank facets filled from LLM sibling slots, literal enums, and
 *       narrow by-id shapes (including past {@code who approv} + id)
 *   <li>Third-party “permissions of/for …” → {@code person_permissions} (not {@code me})
 *   <li>Open narrative / denial-activity audit prose (no entity id) → {@code vector}
 * </ul>
 *
 * <p>Do not add undeclared path-force regex outside this class.
 */
public final class RouteClamps {

  private static final Pattern WHO_APPROVED =
      Pattern.compile("\\bwho\\s+approv", Pattern.CASE_INSENSITIVE);
  private static final Pattern WHO_CAN_APPROVE =
      Pattern.compile("\\bwho\\s+can\\s+approv", Pattern.CASE_INSENSITIVE);

  /** Open prose / audit narratives — must stay on vector (no LLM Cypher planning). */
  private static final Pattern OPEN_NARRATIVE =
      Pattern.compile(
          "(?i)\\b(brief\\s+)?narrative\\b|"
              + "\\bwrite\\s+(me\\s+)?(a\\s+)?(brief\\s+)?(narrative|summary|overview|story)\\b|"
              + "\\brecent\\s+policy\\s+denial\\s+activity\\b|"
              + "\\bdenial\\s+activity\\b.+\\baudit\\s+log\\b|"
              + "\\baudit\\s+log\\b.+\\b(denial|activity)\\b");

  private static final Set<String> OPEN_NARRATIVE_CLAMP_PATHS =
      Set.of("graph", "hybrid", "eligibility", "neo4j_direct", "full_rag");

  private static final Set<String> ENTITY_API_STEAL_PATHS =
      Set.of("neo4j_direct", "graph", "hybrid", "eligibility", "vector", "full_rag");

  private RouteClamps() {}

  public static RouterDecision apply(RouterDecision decision, String question) {
    if (decision == null) {
      return null;
    }
    decision = clampPersonPermissions(decision, question);
    decision = clampEntityApi(decision, question);
    return clampOpenNarrativeToVector(decision, question);
  }

  /**
   * Named-person directory permissions must not land on {@code me} / my_permissions.
   */
  private static RouterDecision clampPersonPermissions(RouterDecision decision, String question) {
    String extracted = PersonQueryParser.extract(question);
    if (!StringUtils.hasText(extracted)) {
      return decision;
    }
    String path = decision.getPath() == null ? "" : decision.getPath().toLowerCase(Locale.ROOT);
    if ("person_permissions".equals(path)) {
      if (!StringUtils.hasText(decision.getPersonQuery())) {
        decision.setPersonQuery(extracted);
      }
      return decision;
    }
    if (!"me".equals(path) && !"eligibility".equals(path)) {
      return decision;
    }
    String prior = decision.getPath();
    decision.setPath("person_permissions");
    if (!StringUtils.hasText(decision.getPersonQuery())) {
      decision.setPersonQuery(extracted);
    }
    appendReasoning(decision, "clamped person_permissions (named person; was " + prior + ")");
    return decision;
  }

  /**
   * Prefer instruction/payment domain APIs; enrich blank facets from slots / stable tokens /
   * narrow by-id shapes.
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

  private static RouterDecision clampOpenNarrativeToVector(
      RouterDecision decision, String question) {
    if (!isOpenNarrativeQuestion(question)) {
      return decision;
    }
    String path = decision.getPath() == null ? "" : decision.getPath().toLowerCase(Locale.ROOT);
    if ("vector".equals(path)) {
      return decision;
    }
    if (!OPEN_NARRATIVE_CLAMP_PATHS.contains(path)) {
      return decision;
    }
    String prior = decision.getPath();
    decision.setPath("vector");
    appendReasoning(decision, "forced vector for open narrative (was " + prior + ")");
    return decision;
  }

  private static void appendReasoning(RouterDecision decision, String note) {
    String reasoning = decision.getReasoning() == null ? "" : decision.getReasoning().trim();
    decision.setReasoning(reasoning.isEmpty() ? note : reasoning + "; " + note);
  }

  /** True for past-tense who-approved audit (not eligibility who-can / creator+approver combo). */
  static boolean isPastWhoApprovedAudit(String question) {
    String text = question == null ? "" : question;
    if (EntityApiQuestion.isCreatorAndApproverShape(text)) {
      return false;
    }
    if (!WHO_APPROVED.matcher(text).find()) {
      return false;
    }
    return !WHO_CAN_APPROVE.matcher(text).find();
  }

  static boolean isOpenNarrativeQuestion(String question) {
    if (question == null || question.isBlank()) {
      return false;
    }
    if (hasEntityId(question)) {
      return false;
    }
    return OPEN_NARRATIVE.matcher(question.strip()).find();
  }

  static boolean hasEntityId(String question) {
    return PaymentIdParser.extract(question).isPresent()
        || InstructionIdParser.extract(question).isPresent();
  }
}
