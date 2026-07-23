package com.sanjuthomas.policypilot.cypher;

import java.util.List;
import java.util.Map;

/** In-process graph plan DTOs (formerly the cypher-builder-svc HTTP contract). */
public final class GraphPlanModels {

  private GraphPlanModels() {}

  public record PlannedQuery(String label, String cypher) {}

  public record PlanResponse(
      boolean matched,
      String intentId,
      String strategy,
      List<PlannedQuery> planned,
      Map<String, Object> meta) {

    public static PlanResponse unmatched() {
      return new PlanResponse(false, null, null, List.of(), Map.of());
    }

    public static PlanResponse matched(
        String intentId, List<PlannedQuery> planned, Map<String, Object> meta) {
      return new PlanResponse(true, intentId, "neo4j_direct", planned, meta);
    }
  }

  public record ValidateResult(boolean ok, String cypher, String error) {
    public static ValidateResult ok(String cypher) {
      return new ValidateResult(true, cypher, null);
    }

    public static ValidateResult fail(String error) {
      return new ValidateResult(false, null, error);
    }
  }
}
