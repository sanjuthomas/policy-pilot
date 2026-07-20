package com.policypilot.chatj.pipeline;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public class RouterDecision {

  private String path;
  private String strategy;
  private String eligibilityTarget;
  private String eligibilityAction;
  private String skill;
  private String meKind;
  private String meAction;
  private String meEntityType;
  private String policyDomain;
  private String policyAction;
  private String personQuery;
  private String reasoning = "";

  public String getPath() {
    return path;
  }

  public void setPath(String path) {
    this.path = path;
  }

  public String getStrategy() {
    return strategy;
  }

  public void setStrategy(String strategy) {
    this.strategy = strategy;
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

  public void normalize() {
    if (!hasText(path) && hasText(strategy)) {
      path = strategy;
    }
    if (isRetrievalPath(path) && !hasText(strategy)) {
      strategy = path;
    }
    if (!hasText(path)) {
      path = "neo4j_direct";
      strategy = null;
    }
    if ("eligibility".equals(path) && !hasText(eligibilityAction)) {
      eligibilityAction = "APPROVE";
    }
    if ("eligibility".equals(path) && !hasText(eligibilityTarget)) {
      eligibilityTarget = "payment";
    }
  }

  private static boolean isRetrievalPath(String value) {
    return "eligibility".equals(value)
        || "graph".equals(value)
        || "vector".equals(value)
        || "hybrid".equals(value);
  }

  private static boolean hasText(String value) {
    return value != null && !value.isBlank();
  }
}
