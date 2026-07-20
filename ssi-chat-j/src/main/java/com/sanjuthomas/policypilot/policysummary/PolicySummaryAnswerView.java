package com.sanjuthomas.policypilot.policysummary;

import java.util.List;

/** View model for normative OPA policy-summary answers. */
public record PolicySummaryAnswerView(
    String title, String domain, String action, String narrative, List<RequirementRow> requires) {

  public PolicySummaryAnswerView {
    if (requires == null) {
      requires = List.of();
    } else {
      requires = List.copyOf(requires);
    }
  }

  public record RequirementRow(String kind, String value) {}
}
