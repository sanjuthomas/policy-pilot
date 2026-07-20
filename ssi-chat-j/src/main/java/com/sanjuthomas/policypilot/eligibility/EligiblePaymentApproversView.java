package com.sanjuthomas.policypilot.eligibility;

import java.util.List;

/**
 * Structured state for the {@code eligible-payment-approvers} answer template.
 *
 * <p>Presentation (prose, tables, money / basis formatting) lives in Thymeleaf — this record only
 * carries API-derived fields.
 */
public record EligiblePaymentApproversView(
    String paymentId,
    String status,
    Object amount,
    String currency,
    String owningLob,
    String instructionId,
    String instructionStatus,
    String blockedReason,
    List<ApproverRow> eligible,
    List<ApproverRow> prospectiveEligible,
    Integer candidatesEvaluated) {

  public record ApproverRow(
      String displayName, String userId, String title, List<String> allowBasis) {}
}
