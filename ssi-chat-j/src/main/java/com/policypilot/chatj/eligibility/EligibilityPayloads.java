package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.eligibility.EligiblePaymentApproversView.ApproverRow;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.util.StringUtils;

/** Shared mapping from eligibility API JSON maps → view-model rows (state only). */
public final class EligibilityPayloads {

  private EligibilityPayloads() {}

  public static List<ApproverRow> toApproverRows(Object eligible) {
    List<ApproverRow> rows = new ArrayList<>();
    for (Map<String, Object> row : castListOfMaps(eligible)) {
      rows.add(
          new ApproverRow(
              blankToNull(str(row.get("display_name"))),
              blankToNull(str(row.get("user_id"))),
              blankToNull(str(row.get("title"))),
              stringList(row.get("allow_basis"))));
    }
    return List.copyOf(rows);
  }

  public static Integer parseCandidatesEvaluated(Object evaluated) {
    if (evaluated instanceof Number number) {
      return number.intValue();
    }
    if (evaluated != null && StringUtils.hasText(str(evaluated))) {
      try {
        return Integer.parseInt(str(evaluated));
      } catch (NumberFormatException ignored) {
        return null;
      }
    }
    return null;
  }

  public static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }

  public static String blankToNull(String value) {
    return StringUtils.hasText(value) ? value : null;
  }

  public static String blockedOrNull(Object value) {
    String text = str(value);
    return StringUtils.hasText(text) ? text : null;
  }

  @SuppressWarnings("unchecked")
  public static List<Map<String, Object>> castListOfMaps(Object value) {
    if (!(value instanceof List<?> list)) {
      return List.of();
    }
    return list.stream()
        .filter(Map.class::isInstance)
        .map(item -> (Map<String, Object>) item)
        .toList();
  }

  private static List<String> stringList(Object value) {
    if (!(value instanceof List<?> list) || list.isEmpty()) {
      return List.of();
    }
    List<String> out = new ArrayList<>();
    for (Object item : list) {
      if (item != null && StringUtils.hasText(String.valueOf(item))) {
        out.add(String.valueOf(item));
      }
    }
    return List.copyOf(out);
  }
}
