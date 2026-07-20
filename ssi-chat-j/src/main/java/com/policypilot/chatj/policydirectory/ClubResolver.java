package com.policypilot.chatj.policydirectory;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Resolve amount-limit clubs from router slots + OPA catalog after {@code path=policy_directory}.
 *
 * <p>Amount / strictness come only from {@code RouterDecision} (LLM). Explicit {@code UP_TO_*_CLUB}
 * tokens may still be read from the message as a stable id slot. Deterministic club math uses the
 * OPA catalog only — not intent classification and not amount regex NLU.
 */
public final class ClubResolver {

  /** Slot: explicit {@code UP_TO_*_CLUB} token in the question (stable id, not NLU). */
  private static final Pattern AMOUNT_CLUB =
      Pattern.compile("\\b(UP_TO_\\d+_(?:MILLION|BILLION)_CLUB)\\b", Pattern.CASE_INSENSITIVE);

  private ClubResolver() {}

  public record ClubResolution(List<String> clubs, Double amount, boolean strict) {}

  /**
   * @param directoryAmount LLM {@code RouterDecision.directoryAmount} (required for amount clubs)
   * @param directoryAmountStrict LLM slot; defaults to {@code true} when amount is set and strict
   *     is null
   */
  public static ClubResolution resolve(
      String message,
      Double directoryAmount,
      Boolean directoryAmountStrict,
      Map<String, Double> clubLimits,
      double absoluteLimit) {
    Matcher clubMatch = AMOUNT_CLUB.matcher(message == null ? "" : message);
    Double amount = directoryAmount;
    boolean strict = directoryAmountStrict != null ? directoryAmountStrict : true;
    if (clubMatch.find()) {
      return new ClubResolution(List.of(clubMatch.group(1).toUpperCase()), amount, strict);
    }
    if (amount == null) {
      return new ClubResolution(List.of(), null, true);
    }
    return new ClubResolution(
        clubsForAmount(amount, clubLimits, absoluteLimit, strict), amount, strict);
  }

  public static List<String> clubsForAmount(
      double amount, Map<String, Double> clubLimits, double absoluteLimit, boolean strict) {
    if (amount <= 0 || amount > absoluteLimit || clubLimits == null || clubLimits.isEmpty()) {
      return List.of();
    }
    List<Map.Entry<String, Double>> ordered = new ArrayList<>(clubLimits.entrySet());
    ordered.sort(
        Comparator.comparingDouble((Map.Entry<String, Double> e) -> e.getValue())
            .thenComparing(Map.Entry::getKey));
    List<String> clubs = new ArrayList<>();
    for (Map.Entry<String, Double> entry : ordered) {
      double ceiling = entry.getValue();
      if (strict) {
        if (ceiling > amount) {
          clubs.add(entry.getKey());
        }
      } else if (ceiling >= amount) {
        clubs.add(entry.getKey());
      }
    }
    return clubs;
  }
}
