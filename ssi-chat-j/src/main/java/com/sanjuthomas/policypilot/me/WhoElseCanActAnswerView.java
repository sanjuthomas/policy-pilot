package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.eligibility.EligiblePaymentApproversView.ApproverRow;
import java.util.List;

/** View model for {@code templates/answers/who-else-can-act.md}. */
public record WhoElseCanActAnswerView(
    String variant,
    String paymentId,
    String blockedReason,
    List<ApproverRow> others) {}
