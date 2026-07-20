package com.sanjuthomas.policypilot.eligibility;

import com.sanjuthomas.policypilot.eligibility.EligiblePaymentApproversView.ApproverRow;
import java.util.List;

/** State for the {@code eligible-payment-submitters} answer template. */
public record EligiblePaymentSubmittersView(
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
