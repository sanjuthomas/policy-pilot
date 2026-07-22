package com.sanjuthomas.policypilot.routing;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Deterministic <em>post-router</em> path clamps — the documented exception to “path comes from
 * Spring AI only.”
 *
 * <p>Primary intent is still Spring AI structured {@code RouterDecision}. These helpers may rewrite
 * {@code path} <strong>before</strong> {@code ChatPathDispatcher}, matching Python {@code
 * prefer_neo4j_direct_when_matched} / past-tense approval audit routing / {@code
 * prefer_vector_for_open_narrative}.
 *
 * <ul>
 *   <li>Past {@code who approv} + payment/instruction id (not {@code who can approv}) → {@code
 *       neo4j_direct}
 *   <li>Open narrative / denial-activity audit prose (no entity id) → {@code vector}
 * </ul>
 *
 * <p>Java’s open-narrative clamp is slightly broader than Python: it also rewrites {@code
 * neo4j_direct} / {@code eligibility} so those lanes cannot steal the vector golden. See {@code
 * ssi-chat-j/AGENTS.md} and {@code .cursor/rules/ssi-chat-j-intent-routing.mdc}.
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

  private RouteClamps() {}

  public static RouterDecision apply(RouterDecision decision, String question) {
    if (decision == null) {
      return null;
    }
    decision = clampPastWhoApproved(decision, question);
    return clampOpenNarrativeToVector(decision, question);
  }

  /**
   * Past-tense "who approved &lt;id&gt;" is a graph audit — never live eligibility OPA cards.
   */
  private static RouterDecision clampPastWhoApproved(RouterDecision decision, String question) {
    if (!isPastWhoApprovedAudit(question)) {
      return decision;
    }
    if (!hasEntityId(question)) {
      return decision;
    }
    if ("neo4j_direct".equals(decision.getPath())) {
      return decision;
    }
    String prior = decision.getPath();
    decision.setPath("neo4j_direct");
    appendReasoning(decision, "clamped neo4j_direct (past who-approved audit; was " + prior + ")");
    return decision;
  }

  /**
   * Open narratives stay vector-only (recorded as full_rag). Slightly broader than Python: also
   * clamps neo4j_direct / eligibility, which otherwise steal the denial-activity golden.
   */
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

  static boolean isPastWhoApprovedAudit(String question) {
    String text = question == null ? "" : question;
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
