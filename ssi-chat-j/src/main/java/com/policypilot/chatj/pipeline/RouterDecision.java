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
 * <p>Other fields are path-specific slots; only those relevant to {@code path} are used.
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

  @JsonPropertyDescription("Skill name when path is skill.")
  private String skill;

  @JsonPropertyDescription("Me-intent kind when path is me.")
  private String meKind;

  @JsonPropertyDescription("Action when path is me and the kind requires one.")
  private String meAction;

  @JsonPropertyDescription("Entity kind when path is me and the kind targets an entity.")
  private String meEntityType;

  @JsonPropertyDescription("Domain when path is policy_summary.")
  private String policyDomain;

  @JsonPropertyDescription("Action when path is policy_summary.")
  private String policyAction;

  @JsonPropertyDescription("Person name or id when path is person_permissions.")
  private String personQuery;

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

  public String getSkill() {
    return skill;
  }

  public void setSkill(String skill) {
    this.skill = skill;
  }

  public String getMeKind() {
    return meKind;
  }

  public void setMeKind(String meKind) {
    this.meKind = meKind;
  }

  public String getMeAction() {
    return meAction;
  }

  public void setMeAction(String meAction) {
    this.meAction = meAction;
  }

  public String getMeEntityType() {
    return meEntityType;
  }

  public void setMeEntityType(String meEntityType) {
    this.meEntityType = meEntityType;
  }

  public String getPolicyDomain() {
    return policyDomain;
  }

  public void setPolicyDomain(String policyDomain) {
    this.policyDomain = policyDomain;
  }

  public String getPolicyAction() {
    return policyAction;
  }

  public void setPolicyAction(String policyAction) {
    this.policyAction = policyAction;
  }

  public String getPersonQuery() {
    return personQuery;
  }

  public void setPersonQuery(String personQuery) {
    this.personQuery = personQuery;
  }

  public String getReasoning() {
    return reasoning;
  }

  public void setReasoning(String reasoning) {
    this.reasoning = reasoning == null ? "" : reasoning;
  }
}
