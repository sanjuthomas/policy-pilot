package com.sanjuthomas.policypilot.me;

import java.util.List;

/** View model for {@code templates/answers/who-covers-lob.md}. */
public record WhoCoversLobAnswerView(
    String variant, String lob, int matchCount, List<WhoCoversLobRow> users) {

  public record WhoCoversLobRow(String displayName, String userId, String title, String roles, String coveringLobs) {}
}
