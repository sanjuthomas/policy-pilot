package com.policypilot.chatj.policysummary;

import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.IdentityTokenFormat;
import com.policypilot.chatj.policysummary.PolicySummaryAnswerView.RequirementRow;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/** Maps authz policy-summary JSON → Thymeleaf view (parity with Python formatter). */
@Component
public class PolicySummaryAnswerFormatter {

  private static final String TEMPLATE = "policy-summary";

  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public PolicySummaryAnswerFormatter(
      AnswerRenderer answerRenderer, IdentityTokenFormat identityTokenFormat) {
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public String format(Map<String, Object> data) {
    return answerRenderer.render(TEMPLATE, toView(data));
  }

  PolicySummaryAnswerView toView(Map<String, Object> data) {
    String title = blankTo("Policy summary", str(data.get("title")));
    String domain = str(data.get("domain")).strip();
    String action = str(data.get("action")).strip();
    String narrative = identityTokenFormat.formatTokensInText(str(data.get("narrative")).strip());

    List<RequirementRow> rows = new ArrayList<>();
    Object requires = data.get("requires");
    if (requires instanceof List<?> list) {
      for (Object item : list) {
        if (!(item instanceof Map<?, ?> map)) {
          continue;
        }
        String kind = str(map.get("kind")).strip();
        String value = str(map.get("value")).strip();
        if (kind.isEmpty() || value.isEmpty()) {
          continue;
        }
        rows.add(new RequirementRow(kind, identityTokenFormat.formatToken(value)));
      }
    }
    return new PolicySummaryAnswerView(title, domain, action, narrative, rows);
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }

  private static String blankTo(String fallback, String value) {
    String trimmed = value == null ? "" : value.strip();
    return trimmed.isEmpty() ? fallback : trimmed;
  }
}
