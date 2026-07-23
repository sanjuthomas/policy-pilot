package com.sanjuthomas.policypilot.extraction;

import java.util.List;

/** View model for instruction / payment version history tables. */
public record EntityVersionsTableView(
    String entityId, String emptyMessage, boolean payment, List<VersionRow> rows) {

  public record VersionRow(
      String versionNumber,
      String status,
      String amount,
      String currency,
      String createdAt,
      String creatorDisplay,
      String approverDisplay) {}
}
