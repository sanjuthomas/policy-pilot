package com.sanjuthomas.policypilot.neo4j;

import java.util.List;

/** View model for {@code templates/answers/security-event-alert-ranking.md}. */
public record SecurityEventAlertRankingView(
    String domainLabel, String periodLabel, List<RankingRow> rows) {

  public record RankingRow(
      String actorDisplay,
      String userId,
      long alertCount,
      long paymentAlerts,
      long instructionAlerts) {}
}
