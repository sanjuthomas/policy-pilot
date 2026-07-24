package com.sanjuthomas.policypilot.skill;

import java.util.List;

/**
 * Outcome of a skill phase (phase-1 preflight or confirm) ready for the chat UI. Mirrors Python
 * {@code chat_application.skills.models.SkillRunResult}.
 */
public record SkillRunResult(
    String answer,
    List<String> activities,
    String pendingId,
    ConfirmationCard confirmation,
    String intentId,
    String skill) {

  public SkillRunResult {
    activities = activities == null ? List.of() : List.copyOf(activities);
  }

  /** Terminal result (no confirmation card / pending). */
  public static SkillRunResult terminal(String answer, List<String> activities, String intentId, String skill) {
    return new SkillRunResult(answer, activities, null, null, intentId, skill);
  }

  /** Phase-1 awaiting-confirmation result carrying a pending id + card. */
  public static SkillRunResult awaiting(
      String answer,
      List<String> activities,
      String pendingId,
      ConfirmationCard confirmation,
      String intentId,
      String skill) {
    return new SkillRunResult(answer, activities, pendingId, confirmation, intentId, skill);
  }

  public boolean hasConfirmation() {
    return pendingId != null && confirmation != null;
  }
}
