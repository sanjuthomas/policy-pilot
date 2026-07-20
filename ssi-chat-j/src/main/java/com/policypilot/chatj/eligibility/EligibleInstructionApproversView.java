package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.eligibility.EligiblePaymentApproversView.ApproverRow;
import java.util.List;

/** State for the {@code eligible-instruction-approvers} answer template. */
public record EligibleInstructionApproversView(
    String instructionId,
    String status,
    String instructionType,
    String owningLob,
    String createdByUserId,
    String createdByTitle,
    String blockedReason,
    List<ApproverRow> eligible,
    List<ApproverRow> prospectiveEligible,
    Integer candidatesEvaluated) {}
