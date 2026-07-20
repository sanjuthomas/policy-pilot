package com.policypilot.chatj.routing;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Slot parsing for sequence instruction ids ({@code YYYYMMDD-LOB-I-n}) — not intent
 * classification.
 */
public final class InstructionIdParser {

  private static final Pattern SEQUENCE_INSTRUCTION_IN_TEXT =
      Pattern.compile("\\d{7,8}-[A-Za-z0-9_]+-I-\\d+", Pattern.CASE_INSENSITIVE);

  private static final Pattern SEQUENCE_INSTRUCTION =
      Pattern.compile(
          "^(?<date>\\d{7,8})-(?<lob>[A-Za-z0-9_]+)-I-(?<seq>\\d+)$", Pattern.CASE_INSENSITIVE);

  private static final Pattern LEGACY_INSTRUCTION_SLOT =
      Pattern.compile("(?i)\\binstruction\\s+([A-Za-z0-9._:-]+)");

  private InstructionIdParser() {}

  public static Optional<String> extract(String question) {
    String text = question == null ? "" : question;
    Matcher sequence = SEQUENCE_INSTRUCTION_IN_TEXT.matcher(text);
    if (sequence.find()) {
      return normalize(sequence.group());
    }
    Matcher legacy = LEGACY_INSTRUCTION_SLOT.matcher(text);
    if (legacy.find()) {
      String token = legacy.group(1).replaceAll("[?.!,;:]+$", "");
      Optional<String> asSequence = normalize(token);
      return asSequence.isPresent() ? asSequence : Optional.of(token);
    }
    return Optional.empty();
  }

  static Optional<String> normalize(String raw) {
    Matcher match = SEQUENCE_INSTRUCTION.matcher(raw.trim());
    if (!match.matches()) {
      return Optional.empty();
    }
    String dateDigits = normalizeDateDigits(match.group("date"));
    if (dateDigits == null) {
      return Optional.empty();
    }
    String lob = match.group("lob").toUpperCase();
    int seq = Integer.parseInt(match.group("seq"));
    return Optional.of(dateDigits + "-" + lob + "-I-" + seq);
  }

  private static String normalizeDateDigits(String datePart) {
    if (datePart.length() == 8) {
      return datePart;
    }
    if (datePart.length() == 7 && datePart.startsWith("0")) {
      return "2" + datePart;
    }
    return null;
  }
}
