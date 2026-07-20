package com.sanjuthomas.policypilot.policydirectory;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * Policy directory lane: amount-club / covering-LOB funding-approver lists via authz (not live OPA
 * eligibility for a payment id).
 */
@Component
public class PolicyDirectoryService {

  private final EligibilityClient eligibilityClient;
  private final PolicyDirectoryAnswerFormatter answerFormatter;

  public PolicyDirectoryService(
      EligibilityClient eligibilityClient, PolicyDirectoryAnswerFormatter answerFormatter) {
    this.eligibilityClient = eligibilityClient;
    this.answerFormatter = answerFormatter;
  }

  public String answer(String message, Subject subject, RouterDecision decision) {
    Double amount = decision != null ? decision.getDirectoryAmount() : null;
    Boolean strict = decision != null ? decision.getDirectoryAmountStrict() : null;
    String coveringLob = decision != null ? decision.getDirectoryCoveringLob() : null;

    Map<String, Double> clubLimits = Map.of();
    double absoluteLimit = 0;
    if (amount != null) {
      Map<String, Object> limits =
          eligibilityClient.paymentAmountLimits(subject.bearerToken(), subject.sessionId());
      clubLimits = toClubLimits(limits.get("club_limits"));
      absoluteLimit = toDouble(limits.get("absolute_limit"));
      if (clubLimits.isEmpty() || absoluteLimit <= 0) {
        return "Could not load payment amount limits from policy (OPA). "
            + "Try again shortly, or ask with an explicit club name such as "
            + "UP_TO_100_BILLION_CLUB.";
      }
    }

    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(message, amount, strict, coveringLob, clubLimits, absoluteLimit);
    if (resolution.clubs().isEmpty()) {
      return "I could not determine which payment amount-limit club or desk LOB applies. "
          + "Try including an amount (e.g. a billion dollars / $25 billion), a club name such as "
          + "UP_TO_100_BILLION_CLUB, or a covering LOB such as FICC.";
    }

    List<Map<String, Object>> merged = new ArrayList<>();
    for (String group : resolution.clubs()) {
      Map<String, Object> data =
          eligibilityClient.groupMembers(
              group,
              subject.bearerToken(),
              subject.sessionId(),
              "FUNDING_APPROVER",
              resolution.coveringLob());
      Object members = data.get("members");
      if (members instanceof List<?> list) {
        for (Object item : list) {
          if (item instanceof Map<?, ?> map) {
            @SuppressWarnings("unchecked")
            Map<String, Object> row = (Map<String, Object>) map;
            merged.add(row);
          }
        }
      }
    }

    return answerFormatter.format(
        resolution.clubs(),
        resolution.amount(),
        resolution.strict(),
        resolution.coveringLob(),
        DirectoryMemberMerger.merge(merged));
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Double> toClubLimits(Object raw) {
    Map<String, Double> out = new HashMap<>();
    if (!(raw instanceof Map<?, ?> map)) {
      return out;
    }
    for (Map.Entry<?, ?> entry : map.entrySet()) {
      if (entry.getKey() == null || entry.getValue() == null) {
        continue;
      }
      try {
        out.put(String.valueOf(entry.getKey()), toDouble(entry.getValue()));
      } catch (NumberFormatException ignored) {
        // skip unusable ceiling
      }
    }
    return out;
  }

  private static double toDouble(Object value) {
    if (value instanceof Number n) {
      return n.doubleValue();
    }
    return Double.parseDouble(String.valueOf(value));
  }
}
