package com.policypilot.chatj.routing;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Slot parsing only — not intent classification.
 *
 * <p>Prefers Policy Pilot sequence payment ids ({@code YYYYMMDD-LOB-P-n}), matching Python
 * {@code extract_payment_ids}. Falls back to {@code payment &lt;token&gt;} for legacy tokens.
 */
public final class PaymentIdParser {

  /** Sequence payment id in free text (see {@code cypher_builder.entity_id}). */
  private static final Pattern SEQUENCE_PAYMENT_IN_TEXT =
      Pattern.compile("\\d{7,8}-[A-Za-z0-9_]+-P-\\d+", Pattern.CASE_INSENSITIVE);

  private static final Pattern SEQUENCE_PAYMENT =
      Pattern.compile(
          "^(?<date>\\d{7,8})-(?<lob>[A-Za-z0-9_]+)-P-(?<seq>\\d+)$", Pattern.CASE_INSENSITIVE);

  private static final Pattern LEGACY_PAYMENT_SLOT =
      Pattern.compile("(?i)\\bpayment\\s+([A-Za-z0-9._:-]+)");

  private PaymentIdParser() {}

  public static Optional<String> extract(String question) {
    String text = question == null ? "" : question;
    Matcher sequence = SEQUENCE_PAYMENT_IN_TEXT.matcher(text);
    if (sequence.find()) {
      return normalizeSequencePayment(sequence.group());
    }
    Matcher legacy = LEGACY_PAYMENT_SLOT.matcher(text);
    if (legacy.find()) {
      return Optional.of(legacy.group(1).replaceAll("[?.!,;:]+$", ""));
    }
    return Optional.empty();
  }

  static Optional<String> normalizeSequencePayment(String raw) {
    Matcher match = SEQUENCE_PAYMENT.matcher(raw.trim());
    if (!match.matches()) {
      return Optional.empty();
    }
    String dateDigits = normalizeDateDigits(match.group("date"));
    if (dateDigits == null) {
      return Optional.empty();
    }
    String lob = match.group("lob").toUpperCase();
    int seq = Integer.parseInt(match.group("seq"));
    return Optional.of(dateDigits + "-" + lob + "-P-" + seq);
  }

  /** Repair common 7-digit typo {@code 0260704} → {@code 20260704}. */
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
