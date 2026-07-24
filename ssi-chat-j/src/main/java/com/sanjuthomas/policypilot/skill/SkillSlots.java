package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Locale;
import java.util.Optional;
import org.springframework.util.StringUtils;

/**
 * Resolves payment-skill slots from {@link RouterDecision} LLM fields. Amount and value date come
 * only from the model — no free-text amount/date regex. Sequence ids prefer LLM slots, with a
 * documented stable-token fallback via {@link InstructionIdParser} / {@link PaymentIdParser}.
 */
public final class SkillSlots {

  private SkillSlots() {}

  /** Create-payment slots once intent is known. */
  public record CreateParams(String instructionId, double amount, String valueDate) {}

  public static Optional<CreateParams> resolveCreate(RouterDecision decision, String message) {
    Optional<String> instructionId = resolveInstructionId(decision, message);
    Double amount = resolveAmount(decision);
    String valueDate = resolveValueDate(decision == null ? null : decision.getSkillValueDate());
    if (instructionId.isEmpty() || amount == null || valueDate == null) {
      return Optional.empty();
    }
    return Optional.of(new CreateParams(instructionId.get(), amount, valueDate));
  }

  public static Optional<String> resolvePaymentId(RouterDecision decision, String message) {
    if (decision != null && StringUtils.hasText(decision.getSkillPaymentId())) {
      Optional<String> fromSlot = PaymentIdParser.extract(decision.getSkillPaymentId().strip());
      if (fromSlot.isPresent()) {
        return fromSlot;
      }
    }
    return PaymentIdParser.extract(message == null ? "" : message);
  }

  static Optional<String> resolveInstructionId(RouterDecision decision, String message) {
    if (decision != null && StringUtils.hasText(decision.getSkillInstructionId())) {
      Optional<String> fromSlot = InstructionIdParser.extract(decision.getSkillInstructionId().strip());
      if (fromSlot.isPresent()) {
        return fromSlot;
      }
    }
    return InstructionIdParser.extract(message == null ? "" : message);
  }

  static Double resolveAmount(RouterDecision decision) {
    if (decision == null || decision.getSkillAmount() == null) {
      return null;
    }
    double amount = decision.getSkillAmount();
    return amount > 0 ? amount : null;
  }

  /**
   * Normalize the LLM {@code skillValueDate} slot: ISO date, or {@code today}/{@code tomorrow}
   * relative to {@code LocalDate.now()}. Does not scan the user message.
   */
  static String resolveValueDate(String skillValueDate) {
    if (!StringUtils.hasText(skillValueDate)) {
      return null;
    }
    String token = skillValueDate.strip();
    String lower = token.toLowerCase(Locale.ROOT);
    if ("today".equals(lower)) {
      return LocalDate.now().toString();
    }
    if ("tomorrow".equals(lower)) {
      return LocalDate.now().plusDays(1).toString();
    }
    try {
      return LocalDate.parse(token).toString();
    } catch (DateTimeParseException ex) {
      return null;
    }
  }
}
