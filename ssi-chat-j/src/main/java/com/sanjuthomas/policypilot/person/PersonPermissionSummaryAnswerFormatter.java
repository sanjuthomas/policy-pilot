package com.sanjuthomas.policypilot.person;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.person.PersonPermissionSummaryAnswerView.CapabilityRow;
import com.sanjuthomas.policypilot.person.PersonPermissionSummaryAnswerView.MatchDetail;
import com.sanjuthomas.policypilot.person.PersonPermissionSummaryAnswerView.MatchRow;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/** Maps authz permission-summary JSON → Thymeleaf (parity with Python formatter). */
@Component
public class PersonPermissionSummaryAnswerFormatter {

  private static final String TEMPLATE = "person-permission-summary";

  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public PersonPermissionSummaryAnswerFormatter(
      AnswerRenderer answerRenderer, IdentityTokenFormat identityTokenFormat) {
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public String format(Map<String, Object> data) {
    return answerRenderer.render(TEMPLATE, toView(data));
  }

  PersonPermissionSummaryAnswerView toView(Map<String, Object> data) {
    String query = str(data.get("query")).strip();
    List<?> rawMatches = data.get("matches") instanceof List<?> list ? list : List.of();

    if (rawMatches.isEmpty()) {
      return new PersonPermissionSummaryAnswerView("empty", query, List.of(), null);
    }

    if (rawMatches.size() > 1) {
      List<MatchRow> rows = new ArrayList<>();
      for (Object item : rawMatches) {
        if (!(item instanceof Map<?, ?> map)) {
          continue;
        }
        rows.add(
            new MatchRow(
                blankTo("—", str(map.get("display_name"))),
                str(map.get("user_id")),
                blankTo("—", str(map.get("title")))));
      }
      return new PersonPermissionSummaryAnswerView("ambiguous", query, rows, null);
    }

    Object only = rawMatches.get(0);
    if (!(only instanceof Map<?, ?> map)) {
      return new PersonPermissionSummaryAnswerView("empty", query, List.of(), null);
    }

    List<String> roles = stringList(map.get("roles"));
    List<String> groups = stringList(map.get("groups"));
    List<String> clubs = stringList(map.get("amount_clubs"));
    List<String> covering = stringList(map.get("covering_lobs"));

    List<CapabilityRow> capabilities = new ArrayList<>();
    Object caps = map.get("capabilities");
    if (caps instanceof List<?> list) {
      for (Object item : list) {
        if (!(item instanceof Map<?, ?> capMap)) {
          continue;
        }
        String kind = str(capMap.get("kind")).strip();
        String description = str(capMap.get("description")).strip();
        if (!kind.isEmpty() && !description.isEmpty()) {
          capabilities.add(new CapabilityRow(kind, description));
        }
      }
    }

    String narrative =
        identityTokenFormat.formatTokensInText(str(map.get("narrative")).strip());
    MatchDetail detail =
        new MatchDetail(
            blankTo("—", str(map.get("display_name"))),
            str(map.get("user_id")),
            blankTo("—", str(map.get("title"))),
            narrative,
            identityTokenFormat.formatTokenList(roles),
            identityTokenFormat.formatTokenList(groups),
            identityTokenFormat.formatTokenList(clubs),
            covering.isEmpty() ? "—" : String.join(", ", covering),
            blankTo("—", str(map.get("lob"))),
            capabilities);
    return new PersonPermissionSummaryAnswerView("single", query, List.of(), detail);
  }

  private static List<String> stringList(Object value) {
    if (!(value instanceof List<?> list)) {
      return List.of();
    }
    List<String> out = new ArrayList<>();
    for (Object item : list) {
      if (item == null) {
        continue;
      }
      String s = String.valueOf(item).strip();
      if (!s.isEmpty()) {
        out.add(s);
      }
    }
    return out;
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }

  private static String blankTo(String fallback, String value) {
    String trimmed = value == null ? "" : value.strip();
    return trimmed.isEmpty() ? fallback : trimmed;
  }
}
