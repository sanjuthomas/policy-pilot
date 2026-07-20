package com.sanjuthomas.policypilot.me;

import java.util.List;

/** View model for {@code templates/answers/waiting-for-me.md}. */
public record WaitingForMeAnswerView(
    String variant, String userId, List<WorklistItem> items) {

  public record WorklistItem(
      String paymentId, Object amount, String currency, String owningLob, String instructionId) {}
}
