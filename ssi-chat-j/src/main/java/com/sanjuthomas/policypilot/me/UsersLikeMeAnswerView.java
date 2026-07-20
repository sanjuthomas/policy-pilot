package com.sanjuthomas.policypilot.me;

import java.util.List;

/** View model for {@code templates/answers/users-like-me.md}. */
public record UsersLikeMeAnswerView(
    String header,
    boolean empty,
    List<MatchRow> matches) {

  public record MatchRow(String displayName, String userId, String title, String why) {}
}
