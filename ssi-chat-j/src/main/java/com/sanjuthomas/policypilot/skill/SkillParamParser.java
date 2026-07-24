package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.time.LocalDate;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Deterministic slot extraction once the skill intent is known (LLM decides the skill). Stable
 * tokens only — instruction/payment id, amount (k/m/b suffixes), value date (today/tomorrow/ISO).
 * Ports the regex from Python {@code chat_application.skills.detect}.
 */
public final class SkillParamParser {

  private SkillParamParser() {}

  /** Create-payment slots: instruction id + amount + value date. */
  public record CreateParams(String instructionId, double amount, String valueDate) {}

  private static final Pattern AMOUNT =
      Pattern.compile(
          "(?:amount\\s*(?:of|=|:)?\\s*|for\\s+)\\$?\\s*([\\d_,]+(?:\\.\\d+)?)\\s*"
              + "(k|thousand|m|mm|million|b|bn|billion)?\\b",
          Pattern.CASE_INSENSITIVE);

  private static final Pattern AMOUNT_WITH_UNIT =
      Pattern.compile(
          "\\$?\\s*([\\d_,]+(?:\\.\\d+)?)\\s*(k|thousand|m|mm|million|b|bn|billion)\\b",
          Pattern.CASE_INSENSITIVE);

  private static final Pattern VALUE_DATE_ISO =
      Pattern.compile(
          "\\b(?:value\\s*date|valuedate)\\s*(?:is|=|:)?\\s*(\\d{4}-\\d{2}-\\d{2})\\b",
          Pattern.CASE_INSENSITIVE);

  private static final Pattern VALUE_DATE_RELATIVE =
      Pattern.compile(
          "\\b(?:value\\s*date|valuedate|settle(?:ment)?\\s*date)\\b\\s*(?:is|=|:)?\\s*"
              + "(today|tomorrow)\\b|\\b(today|tomorrow)\\b.{0,24}\\b(?:value\\s*date|valuedate)\\b",
          Pattern.CASE_INSENSITIVE);

  private static final Pattern TOMORROW = Pattern.compile("\\btomorrow\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern TODAY = Pattern.compile("\\btoday\\b", Pattern.CASE_INSENSITIVE);

  public static Optional<CreateParams> parseCreate(String message) {
    String text = message == null ? "" : message.strip();
    if (text.isEmpty()) {
      return Optional.empty();
    }
    Optional<String> instructionId = InstructionIdParser.extract(text);
    if (instructionId.isEmpty()) {
      return Optional.empty();
    }
    Double amount = parseAmount(text);
    String valueDate = parseValueDate(text);
    if (amount == null || valueDate == null) {
      return Optional.empty();
    }
    return Optional.of(new CreateParams(instructionId.get(), amount, valueDate));
  }

  public static Optional<String> parsePaymentId(String message) {
    return PaymentIdParser.extract(message == null ? "" : message.strip());
  }

  static Double parseAmount(String message) {
    String bestDigits = null;
    String bestUnit = null;
    int bestScore = -1;
    int bestStart = -1;
    for (Pattern pattern : new Pattern[] {AMOUNT, AMOUNT_WITH_UNIT}) {
      Matcher matcher = pattern.matcher(message);
      while (matcher.find()) {
        String unit = matcher.group(2);
        int hasUnit = unit != null && !unit.isEmpty() ? 1 : 0;
        int start = matcher.start();
        // Parity with Python max(candidates, key=(has_unit, start)): prefer a unit, then latest.
        if (hasUnit > bestScore || (hasUnit == bestScore && start >= bestStart)) {
          bestDigits = matcher.group(1);
          bestUnit = unit;
          bestScore = hasUnit;
          bestStart = start;
        }
      }
    }
    if (bestDigits == null) {
      return null;
    }
    String raw = bestDigits.replace(",", "").replace("_", "");
    double value;
    try {
      value = Double.parseDouble(raw);
    } catch (NumberFormatException ex) {
      return null;
    }
    String unit = bestUnit == null ? "" : bestUnit.toLowerCase();
    switch (unit) {
      case "k", "thousand" -> value *= 1_000d;
      case "m", "mm", "million" -> value *= 1_000_000d;
      case "b", "bn", "billion" -> value *= 1_000_000_000d;
      default -> {
        // bare number
      }
    }
    return value <= 0 ? null : value;
  }

  static String parseValueDate(String message) {
    Matcher iso = VALUE_DATE_ISO.matcher(message);
    if (iso.find()) {
      return iso.group(1);
    }
    Matcher relative = VALUE_DATE_RELATIVE.matcher(message);
    if (relative.find()) {
      String token = relative.group(1) != null ? relative.group(1) : relative.group(2);
      if (token != null) {
        return relativeDay(token).toString();
      }
    }
    if (TOMORROW.matcher(message).find()) {
      return LocalDate.now().plusDays(1).toString();
    }
    if (TODAY.matcher(message).find()) {
      return LocalDate.now().toString();
    }
    return null;
  }

  private static LocalDate relativeDay(String token) {
    if ("tomorrow".equalsIgnoreCase(token)) {
      return LocalDate.now().plusDays(1);
    }
    return LocalDate.now();
  }
}
