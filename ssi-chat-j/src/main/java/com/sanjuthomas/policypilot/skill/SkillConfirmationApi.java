package com.sanjuthomas.policypilot.skill;

import java.util.LinkedHashMap;
import java.util.Map;

/** Builds the {@code skill_confirmation} API payload from a phase-1 result. */
public final class SkillConfirmationApi {

  private SkillConfirmationApi() {}

  /** {@code {pending_id, skill, card}} — parity with Python {@code SkillConfirmationInfo}. */
  public static Map<String, Object> from(SkillRunResult result) {
    if (result == null || !result.hasConfirmation()) {
      return null;
    }
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("pending_id", result.pendingId());
    payload.put("skill", result.skill());
    payload.put("card", result.confirmation().toApi());
    return payload;
  }
}
