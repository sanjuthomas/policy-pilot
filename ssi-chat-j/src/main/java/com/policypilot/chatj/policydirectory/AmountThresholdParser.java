package com.policypilot.chatj.policydirectory;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Optional regex fallback for well-formed {@code $N billion} phrases when the router omits
 * {@code directoryAmount}. Primary amount NLU is Spring AI slots on {@code RouterDecision} — not
 * these patterns. Parity helpers: Python {@code payment_amount_threshold_from_question} /
 * {@code is_strict_payment_amount_threshold}.
 */
public final class AmountThresholdParser {

  // --- Fallback slot parsers only (after path=policy_directory). Not primary NLU / routing. ---

  /** Slot: comparison cue + numeric amount (e.g. "more than $25 billion"). */
  private static final Pattern AMOUNT_THRESHOLD =
      Pattern.compile(
          "(?:>|greater\\s+than|more\\s+than|over|above|exceeding|at\\s+least)\\s*"
              + "\\$?\\s*([\\d,]+(?:\\.\\d+)?)\\s*(m(?:illion)?|b(?:illion)?|k(?:ilo)?)?",
          Pattern.CASE_INSENSITIVE);

  /** Slot: bare {@code $N} / {@code $N million} when no comparison phrase matched. */
  private static final Pattern DOLLAR_AMOUNT =
      Pattern.compile(
          "\\$\\s*([\\d,]+(?:\\.\\d+)?)\\s*(m(?:illion)?|b(?:illion)?|k(?:ilo)?)?",
          Pattern.CASE_INSENSITIVE);

  /** Slot: strict vs inclusive comparison wording (not path selection). */
  private static final Pattern STRICT_COMPARISON =
      Pattern.compile(
          "(?:>|greater\\s+than|more\\s+than|over|above|exceeding)\\b", Pattern.CASE_INSENSITIVE);

  private static final Pattern INCLUSIVE_COMPARISON =
      Pattern.compile("\\bat\\s+least\\b", Pattern.CASE_INSENSITIVE);

  private static final Pattern WORTH_MORE_THAN =
      Pattern.compile("\\bworth\\s+more\\s+than\\b", Pattern.CASE_INSENSITIVE);

  private AmountThresholdParser() {}

  public static Optional<Double> parseAmount(String message) {
    if (message == null || message.isBlank()) {
      return Optional.empty();
    }
    Matcher threshold = AMOUNT_THRESHOLD.matcher(message);
    if (threshold.find()) {
      return Optional.of(parseMoney(threshold.group(1), threshold.group(2)));
    }
    Matcher dollar = DOLLAR_AMOUNT.matcher(message);
    while (dollar.find()) {
      double amount = parseMoney(dollar.group(1), dollar.group(2));
      if (amount >= 1_000_000d) {
        return Optional.of(amount);
      }
    }
    return Optional.empty();
  }

  /** True when the question asks strictly above the threshold (more than / exceeding / …). */
  public static boolean isStrict(String message) {
    if (message == null) {
      return true;
    }
    if (INCLUSIVE_COMPARISON.matcher(message).find()) {
      return false;
    }
    if (STRICT_COMPARISON.matcher(message).find()) {
      return true;
    }
    return WORTH_MORE_THAN.matcher(message).find();
  }

  private static double parseMoney(String rawNumber, String suffix) {
    double value = Double.parseDouble(rawNumber.replace(",", ""));
    String unit = suffix == null ? "" : suffix.toLowerCase();
    if (unit.startsWith("b")) {
      return value * 1_000_000_000d;
    }
    if (unit.startsWith("m")) {
      return value * 1_000_000d;
    }
    if (unit.startsWith("k")) {
      return value * 1_000d;
    }
    return value;
  }
}
