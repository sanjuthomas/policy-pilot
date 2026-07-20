package com.sanjuthomas.policypilot.policydirectory;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/** Maps directory API rows → view model; prose is Thymeleaf. */
@Component
public class PolicyDirectoryAnswerFormatter {

  private static final String TEMPLATE = "policy-directory-members";

  private final AnswerRenderer answerRenderer;

  public PolicyDirectoryAnswerFormatter(AnswerRenderer answerRenderer) {
    this.answerRenderer = answerRenderer;
  }

  public String format(
      List<String> groups,
      Double amount,
      boolean strictThreshold,
      String coveringLob,
      List<Map<String, Object>> members) {
    return answerRenderer.render(
        TEMPLATE, toView(groups, amount, strictThreshold, coveringLob, members));
  }

  static PolicyDirectoryAnswerView toView(
      List<String> groups,
      Double amount,
      boolean strictThreshold,
      String coveringLob,
      List<Map<String, Object>> members) {
    List<PolicyDirectoryMemberRow> rows = new ArrayList<>();
    for (Map<String, Object> row : members) {
      rows.add(
          new PolicyDirectoryMemberRow(
              str(row.get("user_id")),
              str(row.get("display_name")),
              str(row.get("title")),
              joinList(row.get("groups")),
              joinList(row.get("covering_lobs"))));
    }
    return new PolicyDirectoryAnswerView(
        groups == null ? List.of() : List.copyOf(groups),
        amount,
        strictThreshold,
        blankToNull(coveringLob),
        rows);
  }

  private static String joinList(Object value) {
    if (!(value instanceof List<?> list) || list.isEmpty()) {
      return null;
    }
    List<String> parts = new ArrayList<>();
    for (Object item : list) {
      if (item != null && !String.valueOf(item).isBlank()) {
        parts.add(String.valueOf(item));
      }
    }
    return parts.isEmpty() ? null : String.join(", ", parts);
  }

  private static String str(Object value) {
    if (value == null) {
      return null;
    }
    String text = String.valueOf(value).trim();
    return text.isEmpty() ? null : text;
  }

  private static String blankToNull(String value) {
    return value == null || value.isBlank() ? null : value;
  }
}
