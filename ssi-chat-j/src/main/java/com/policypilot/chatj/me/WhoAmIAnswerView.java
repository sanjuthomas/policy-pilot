package com.policypilot.chatj.me;

/** View model for {@code templates/answers/who-am-i.md}. */
public record WhoAmIAnswerView(
    String displayName,
    String userId,
    String title,
    String roles,
    String groups,
    String amountClubs,
    String deskLob,
    String coveringLobs,
    String supervisor,
    String audience) {}
