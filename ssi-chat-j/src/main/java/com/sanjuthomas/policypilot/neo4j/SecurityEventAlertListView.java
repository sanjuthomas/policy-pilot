package com.sanjuthomas.policypilot.neo4j;

import java.util.List;

/** View model for {@code templates/answers/security-event-alert-list.md}. */
public record SecurityEventAlertListView(
    String title, String emptyMessage, List<AlertEventRow> rows) {

  public record AlertEventRow(
      String eventId,
      String timestamp,
      String entityType,
      String entityId,
      String actorDisplay,
      String action) {}
}
