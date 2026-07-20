package com.sanjuthomas.policypilot.observability;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import org.springframework.stereotype.Component;

/**
 * Emits {@code chat.skill.outcome.count} for skill-execution OpenSLO. Ready for mutation skills;
 * no-op when {@code intent_id} is not {@code skill.*}.
 */
@Component
public class SkillMetrics {

  private final MeterRegistry meterRegistry;

  public SkillMetrics(MeterRegistry meterRegistry) {
    this.meterRegistry = meterRegistry;
  }

  public void recordSkillOutcome(String intentId) {
    ParsedSkill parsed = parseSkillIntent(intentId);
    if (parsed == null) {
      return;
    }
    meterRegistry
        .counter(
            "chat.skill.outcome.count",
            Tags.of(
                "chat.skill", parsed.skill(),
                "chat.skill.outcome", parsed.outcome(),
                "chat.skill.status", parsed.status()))
        .increment();
  }

  static ParsedSkill parseSkillIntent(String intentId) {
    if (intentId == null || intentId.isBlank()) {
      return null;
    }
    String[] parts = intentId.split("\\.", 3);
    if (parts.length == 0 || !"skill".equals(parts[0])) {
      return null;
    }
    String skill = parts.length >= 2 ? parts[1] : "unknown";
    String outcome = parts.length >= 3 ? parts[2] : "unknown";
    String status = outcome.endsWith("error") ? "error" : "ok";
    return new ParsedSkill(skill, outcome, status);
  }

  record ParsedSkill(String skill, String outcome, String status) {}
}
