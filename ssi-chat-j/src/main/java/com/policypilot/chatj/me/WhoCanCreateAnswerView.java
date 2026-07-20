package com.policypilot.chatj.me;

import java.util.List;

/** View model for {@code templates/answers/who-can-create.md}. */
public record WhoCanCreateAnswerView(
    String variant,
    String lobLabel,
    List<CreatorRow> creators) {

  public record CreatorRow(
      String displayName,
      String userId,
      String title,
      String covering,
      String clubs,
      String groups,
      String supervisor,
      boolean you) {}
}
