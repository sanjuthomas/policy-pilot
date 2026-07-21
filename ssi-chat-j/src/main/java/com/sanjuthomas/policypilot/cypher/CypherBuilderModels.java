package com.sanjuthomas.policypilot.cypher;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

/** DTOs for cypher-builder-svc HTTP contract. */
public final class CypherBuilderModels {

  private CypherBuilderModels() {}

  @JsonInclude(JsonInclude.Include.NON_NULL)
  public record PlanOptions(
      @JsonProperty("lob_scoped") Boolean lobScoped,
      @JsonProperty("allowed_lobs") List<String> allowedLobs) {}

  public record PlanRequest(String question, String mode, PlanOptions options) {
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
