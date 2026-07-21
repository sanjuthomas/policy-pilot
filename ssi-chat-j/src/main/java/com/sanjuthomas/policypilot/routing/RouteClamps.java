package com.sanjuthomas.policypilot.routing;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.regex.Pattern;

/**
 * Deterministic post-router clamps (parity with Python {@code prefer_neo4j_direct_when_matched}
 * and past-tense approval audit routing).
 */
public final class RouteClamps {

  private static final Pattern WHO_APPROVED =
      Pattern.compile("\\bwho\\s+approv", Pattern.CASE_INSENSITIVE);
  private static final Pattern WHO_CAN_APPROVE =
      Pattern.compile("\\bwho\\s+can\\s+approv", Pattern.CASE_INSENSITIVE);

  private RouteClamps() {}

  /**
   * Past-tense "who approved &lt;id&gt;" is a graph audit — never live eligibility OPA cards.
   */
  public static RouterDecision apply(RouterDecision decision, String question) {
    if (decision == null) {
      return null;
    }
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
    String reasoning = decision.getReasoning() == null ? "" : decision.getReasoning().trim();
    String note = "clamped neo4j_direct (past who-approved audit; was " + prior + ")";
    decision.setReasoning(reasoning.isEmpty() ? note : reasoning + "; " + note);
    return decision;
  }

  static boolean isPastWhoApprovedAudit(String question) {
    String text = question == null ? "" : question;
    if (!WHO_APPROVED.matcher(text).find()) {
      return false;
    }
    return !WHO_CAN_APPROVE.matcher(text).find();
  }

  static boolean hasEntityId(String question) {
    return PaymentIdParser.extract(question).isPresent()
        || InstructionIdParser.extract(question).isPresent();
  }
}
