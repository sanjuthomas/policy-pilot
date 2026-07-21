package com.sanjuthomas.policypilot.person;

import java.util.List;

/** View model for {@code templates/answers/person-permission-summary.md}. */
public record PersonPermissionSummaryAnswerView(
    String shape,
    String query,
    List<MatchRow> matches,
    MatchDetail detail) {

  public record MatchRow(String displayName, String userId, String title) {}

  public record CapabilityRow(String kind, String description) {}

  public record MatchDetail(
      String displayName,
      String userId,
      String title,
      String narrative,
      String roles,
      String groups,
      String amountClubs,
      String coveringLobs,
      String deskLob,
      List<CapabilityRow> capabilities) {}
}
