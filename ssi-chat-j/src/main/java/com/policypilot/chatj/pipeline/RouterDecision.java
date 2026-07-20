package com.policypilot.chatj.pipeline;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.Setter;

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
@Getter
@Setter
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

  /**
   * When path is policy_directory: USD amount threshold as a number (e.g. 1e9 for \"a billion\" /
   * \"$1 billion\"). Semantic amount extraction — do not leave null when the question implies a
   * money size.
   */
  @JsonPropertyDescription(
      "policy_directory only: USD threshold as a number (1e9 for a/one/$1 billion).")
  private Double directoryAmount;

  /**
   * When path is policy_directory: true if the threshold is exclusive (more than / exceeding /
   * over); false if inclusive (at least / a N-dollar payment / of N).
   */
  @JsonPropertyDescription(
      "policy_directory only: true for more-than/exceeding; false for at-least / a N payment.")
  private Boolean directoryAmountStrict;

  /**
   * When path is policy_directory: covering desk LOB for funding-approver directory (e.g. FICC,
   * FX). Set when the question asks who may approve payments covering that desk — not when a
   * specific payment id is present (that is eligibility).
   */
  @JsonPropertyDescription(
      "policy_directory only: covering desk LOB code (FICC, FX, …) when asked without a payment id.")
  private String directoryCoveringLob;

  /** When path is policy_summary: payment vs instruction domain. */
  @JsonPropertyDescription("policy_summary only: payment or instruction.")
  private String policyDomain;

  /** When path is policy_summary: OPA action (CREATE, APPROVE, UPDATE, SUBMIT, REJECT, CANCEL). */
  @JsonPropertyDescription("policy_summary only: OPA action (APPROVE default).")
  private String policyAction;

  /** When path is me: which me-centric intent (who_am_i, …). */
  @JsonPropertyDescription("me only: who_am_i (identity), …")
  private String meKind;

  /** Model rationale for logs — not used for dispatch. */
  @JsonPropertyDescription("Brief explanation of the routing choice.")
  @Setter(AccessLevel.NONE)
  private String reasoning = "";

  public void setReasoning(String reasoning) {
    this.reasoning = reasoning == null ? "" : reasoning;
  }
}
