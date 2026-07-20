package com.policypilot.chatj.eligibility;

import java.util.List;

/** View model for {@code templates/answers/eligible-approvers.md}. */
public record EligibleApproversView(
    String paymentId,
    String status,
    String amountText,
    String owningLob,
    String instructionSummary,
    String blockedReason,
    List<ApproverRow> eligible,
    Integer candidatesEvaluated) {

  public record ApproverRow(int index, String name, String title, String policyBasis) {}
}
