package com.sanjuthomas.policypilot.cypher;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

/** DTOs for cypher-builder-svc HTTP contract. */
public final class CypherBuilderModels {

  private CypherBuilderModels() {}

  public record PlanRequest(String question, String mode, Map<String, Object> options) {
    public PlanRequest(String question, String mode) {
      this(question, mode, null);
    }
  }

  @JsonIgnoreProperties(ignoreUnknown = true)
  public record PlannedQuery(String label, String cypher) {}

  @JsonIgnoreProperties(ignoreUnknown = true)
  public record PlanResponse(
      boolean matched,
      @JsonProperty("intent_id") String intentId,
      String strategy,
      List<PlannedQuery> planned,
      Map<String, Object> meta) {}

  public record ValidateRequest(String cypher) {}

  @JsonIgnoreProperties(ignoreUnknown = true)
  public record ValidateResponse(boolean ok, String cypher, String error) {}
}
