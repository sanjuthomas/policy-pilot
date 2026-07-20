package com.policypilot.chatj.me;

import java.util.List;

/** View model for {@code templates/answers/my-permissions.md}. */
public record MyPermissionsAnswerView(
    String displayName,
    String userId,
    String roles,
    String groups,
    String amountClubs,
    String coveringLobs,
    String deskLob,
    List<String> capabilities) {}
