package com.sanjuthomas.policypilot.pipeline;

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

  /**
   * When path is skill: which payment mutation skill to run. Defaults to {@code create_payment}
   * in the skill lane when the model leaves it blank.
   */
  @JsonPropertyDescription(
      "skill only: create_payment|submit_payment|approve_payment|cancel_payment")
  private String skill;

  /**
   * When path is skill and skill=create_payment: sequence instruction id to draft against.
   * Map paraphrases here — the client does not scrape free text for open-vocabulary slots.
   */
  @JsonPropertyDescription(
      "skill create_payment only: instruction sequence id (YYYYMMDD-LOB-I-n)")
  private String skillInstructionId;

  /**
   * When path is skill and skill is submit/approve/cancel: sequence payment id.
   */
  @JsonPropertyDescription(
      "skill submit|approve|cancel only: payment sequence id (YYYYMMDD-LOB-P-n)")
  private String skillPaymentId;

  /**
   * When path is skill and skill=create_payment: USD amount as a number (e.g. 1e6 for \"1 million\").
   * Semantic amount extraction — do not leave null when the question implies a money size.
   */
  @JsonPropertyDescription(
      "skill create_payment only: USD amount as a number (1e6 for 1 million / $1M)")
  private Double skillAmount;

  /**
   * When path is skill and skill=create_payment: settlement / value date. Prefer ISO {@code
   * YYYY-MM-DD}; {@code today} / {@code tomorrow} are also accepted and resolved relative to the
   * date given in the router system prompt.
   */
  @JsonPropertyDescription(
      "skill create_payment only: value date as YYYY-MM-DD (or today|tomorrow)")
  private String skillValueDate;

  @JsonPropertyDescription("Entity kind when path is eligibility.")
  private String eligibilityTarget;

  @JsonPropertyDescription("Action when path is eligibility.")
  private String eligibilityAction;

  /**
   * When path is document_extraction: payment vs instruction entity to load by id via domain API
   * (not Neo4j). Sequence ids encode type (-P- vs -I-); set explicitly when the noun is present.
   */
  @JsonPropertyDescription(
      "document_extraction only: payment or instruction (sequence id encodes type if omitted).")
  private String extractionTarget;

  /**
   * When path is document_extraction: which API facet to answer (full card, status, creator, list,
   * versions, …). Prefer this over regex facet detection.
   */
  @JsonPropertyDescription(
      "document_extraction only: show|status|creator|creator_and_approver|approver|"
          + "list_by_status|list_standing|list_single_use|created_by_user|versions|"
          + "count|group_by_status|group_by_lob")
  private String extractionFacet;

  /**
   * When path is document_extraction and listing/filtering by lifecycle status: domain enum only.
   * Map paraphrases (paused, pending, …) to the enum here — the client does not maintain synonym
   * tables.
   */
  @JsonPropertyDescription(
      "document_extraction list/filter: SUBMITTED|APPROVED|REJECTED|SUSPENDED|EXPIRED|"
          + "CANCELLED|DRAFT|USED (map paraphrases like paused→SUSPENDED)")
  private String entityStatus;

  /**
   * When path is document_extraction and listing by instruction type: domain enum only.
   * Map paraphrases (evergreen, one-time, …) to STANDING or SINGLE_USE.
   */
  @JsonPropertyDescription(
      "document_extraction list/filter: STANDING|SINGLE_USE (map paraphrases like evergreen→STANDING)")
  private String instructionType;

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

  /**
   * When path is person_permissions: person name or user id (e.g. {@code Kowalski, Anna} or {@code
   * pay-203}). Not "my permissions" (that is {@code me} / {@code my_permissions}).
   */
  @JsonPropertyDescription(
      "person_permissions only: person name or user id (e.g. 'Kowalski, Anna' or 'pay-203').")
  private String personQuery;

  /** When path is me: which me-centric intent (who_am_i, my_permissions, …). */
  @JsonPropertyDescription(
      "me only: who_am_i, my_permissions, can_act_on_entity, who_else_can_act, "
          + "who_can_create, who_covers_lob, waiting_for_me, users_like_me")
  private String meKind;

  /** When path is me: OPA-ish action for can_act / who_else / waiting (CREATE, APPROVE, …). */
  @JsonPropertyDescription("me only: CREATE|APPROVE|SUBMIT|CANCEL|… when relevant")
  private String meAction;

  /** When path is me: payment vs instruction for who_can_create / can_act. */
  @JsonPropertyDescription("me only: payment or instruction when relevant")
  private String meEntityType;

  /**
   * When path is neo4j_direct: which deterministic graph plan to run. Map paraphrases here — the
   * Cypher planner does not phrase-match SoD / alert shapes from free text.
   */
  @JsonPropertyDescription(
      "neo4j_direct only: alert_count|alert_list|alert_ranking|self_approval|mutual_approval|"
          + "subordinate_approver|duplicate_routes|cross_entity_reciprocal_approval|"
          + "instruction_timeline")
  private String graphIntent;

  /**
   * Time window for alert/denial aggregates ({@code neo4j_direct}) and inventory counts
   * ({@code document_extraction} + {@code extractionFacet=count}). Map paraphrases here — the
   * formatter does not parse "today"/"this week" from free text.
   */
  @JsonPropertyDescription(
      "neo4j_direct alert aggregates and document_extraction count: "
          + "day|week|month|quarter|year|all (today→day)")
  private String graphTimeWindow;

  /**
   * When path is neo4j_direct for alert/denial aggregates: entity scope for answer wording.
   */
  @JsonPropertyDescription("neo4j_direct alert aggregates: payment|instruction (or omit)")
  private String graphEventScope;

  /**
   * When path is neo4j_direct for alert aggregates: ALERT vs policy-denial wording.
   */
  @JsonPropertyDescription("neo4j_direct alert aggregates: alert|denial|approval_denial")
  private String graphEventKind;

  /** Model rationale for logs — not used for dispatch. */
  @JsonPropertyDescription("Brief explanation of the routing choice.")
  @Setter(AccessLevel.NONE)
  private String reasoning = "";

  public void setReasoning(String reasoning) {
    this.reasoning = reasoning == null ? "" : reasoning;
  }
}
