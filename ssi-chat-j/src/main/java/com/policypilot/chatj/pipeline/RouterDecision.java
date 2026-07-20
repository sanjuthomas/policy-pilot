package com.policypilot.chatj.pipeline;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;

/**
 * Structured output of the <em>route</em> step: one LLM call that decides what this
 * question is, then the orchestrator executes deterministically.
 *
 * <p><b>Vocabulary</b>
 * <ul>
 *   <li><b>Route</b> — the act of producing this object (not a field).</li>
 *   <li><b>path</b> — which handler lane runs. Path is law for dispatch.</li>
 * </ul>
 *
 * <p>Grow this class only when a new path is implemented — add slots then, not ahead of time.
 * Unknown JSON properties from the model are ignored.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public class RouterDecision {

  /** Primary intent lane — the only dispatch key. */
  @JsonPropertyDescription("Primary intent path / handler lane.")
  private String path;

  @JsonPropertyDescription("Entity kind when path is eligibility.")
  private String eligibilityTarget;

  @JsonPropertyDescription("Action when path is eligibility.")
  private String eligibilityAction;

  /** Model rationale for logs — not used for dispatch. */
  @JsonPropertyDescription("Brief explanation of the routing choice.")
  private String reasoning = "";

  public String getPath() {
    return path;
  }

  public void setPath(String path) {
    this.path = path;
  }

  public String getEligibilityTarget() {
    return eligibilityTarget;
  }

  public void setEligibilityTarget(String eligibilityTarget) {
    this.eligibilityTarget = eligibilityTarget;
  }

  public String getEligibilityAction() {
    return eligibilityAction;
  }

  public void setEligibilityAction(String eligibilityAction) {
    this.eligibilityAction = eligibilityAction;
  }

  public String getReasoning() {
    return reasoning;
  }

  public void setReasoning(String reasoning) {
    this.reasoning = reasoning == null ? "" : reasoning;
  }
}
