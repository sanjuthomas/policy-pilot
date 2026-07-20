package com.policypilot.chatj.policydirectory;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.util.StringUtils;

/**
 * Resolve amount-limit / covering-LOB directory groups from router slots + OPA catalog after
 * {@code path=policy_directory}.
 *
 * <p>Amount / strictness / covering LOB come from {@code RouterDecision} (LLM). Explicit {@code
 * UP_TO_*_CLUB} tokens may still be read from the message as a stable id slot. Deterministic club
 * math uses the OPA catalog only.
 */
public final class ClubResolver {

  /** Org group used when listing funding approvers by covering LOB (no amount club). */
  public static final String FUNDING_APPROVER_ORG_GROUP = "MIDDLE_OFFICE";

  /** Slot: explicit {@code UP_TO_*_CLUB} token in the question (stable id, not NLU). */
  private static final Pattern AMOUNT_CLUB =
      Pattern.compile("\\b(UP_TO_\\d+_(?:MILLION|BILLION)_CLUB)\\b", Pattern.CASE_INSENSITIVE);

  private ClubResolver() {}

  public record ClubResolution(
      List<String> clubs, Double amount, boolean strict, String coveringLob) {}

  /**
   * @param directoryAmount LLM amount slot (optional)
   * @param directoryAmountStrict LLM strictness; defaults to true when amount set and strict null
   * @param directoryCoveringLob LLM covering desk LOB (optional)
   * @param clubLimits OPA catalog; may be empty when only covering LOB is used
   */
  public static ClubResolution resolve(
      String message,
      Double directoryAmount,
      Boolean directoryAmountStrict,
      String directoryCoveringLob,
      Map<String, Double> clubLimits,
      double absoluteLimit) {
    Matcher clubMatch = AMOUNT_CLUB.matcher(message == null ? "" : message);
    Double amount = directoryAmount;
    boolean strict = directoryAmountStrict != null ? directoryAmountStrict : true;
    String coveringLob =
        StringUtils.hasText(directoryCoveringLob) ? directoryCoveringLob.trim().toUpperCase() : null;

    if (clubMatch.find()) {
      return new ClubResolution(
          List.of(clubMatch.group(1).toUpperCase()), amount, strict, coveringLob);
    }
    if (amount != null) {
      return new ClubResolution(
          clubsForAmount(amount, clubLimits, absoluteLimit, strict), amount, strict, coveringLob);
    }
    if (coveringLob != null) {
      return new ClubResolution(List.of(FUNDING_APPROVER_ORG_GROUP), null, true, coveringLob);
    }
    return new ClubResolution(List.of(), null, true, null);
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
