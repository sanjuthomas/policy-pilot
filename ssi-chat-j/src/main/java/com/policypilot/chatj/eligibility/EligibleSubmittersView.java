package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.eligibility.EligibleApproversView.ApproverRow;
import java.util.List;

/** State for the eligible-submitters answer template. */
public record EligibleSubmittersView(
    String paymentId,
    String status,
    Object amount,
    String currency,
    String owningLob,
    String instructionId,
    String instructionStatus,
    String submitBlockedReason,
    List<ApproverRow> eligible,
    Integer candidatesEvaluated) {}
