package com.policypilot.chatj.me;

import java.util.List;

/** View model for {@code templates/answers/can-act-on-entity.md}. */
public record CanActOnEntityAnswerView(
    String variant,
    String userId,
    String displayName,
    String title,
    String deskLob,
    String coveringLobs,
    String amountClubs,
    String entityId,
    List<String> gaps,
    String extra) {

  public static CanActOnEntityAnswerView of(
      String variant,
      String userId,
      String displayName,
      String title,
      String deskLob,
      String coveringLobs,
      String amountClubs,
      String entityId,
      List<String> gaps,
      String extra) {
    return new CanActOnEntityAnswerView(
        variant,
        userId,
        displayName,
        title,
        deskLob,
        coveringLobs,
        amountClubs,
        entityId,
        gaps == null ? List.of() : gaps,
        extra == null ? "" : extra);
  }
}
