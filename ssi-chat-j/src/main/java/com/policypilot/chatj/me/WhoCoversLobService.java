package com.policypilot.chatj.me;

import com.policypilot.chatj.auth.ChatUsersDirectory;
import com.policypilot.chatj.auth.DirectoryUser;
import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.IdentityTokenFormat;
import com.policypilot.chatj.me.WhoCoversLobAnswerView.WhoCoversLobRow;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Parity with Python {@code who_covers_lob.py}. */
@Component
public class WhoCoversLobService {

  private static final String TEMPLATE = "who-covers-lob";

  private final ChatUsersDirectory directory;
  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public WhoCoversLobService(
      ChatUsersDirectory directory,
      AnswerRenderer answerRenderer,
      IdentityTokenFormat identityTokenFormat) {
    this.directory = directory;
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public MeIntentResult answer(MeIntent intent) {
    if (!StringUtils.hasText(intent.coveringLob())) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WhoCoversLobAnswerView("need_lob", null, 0, List.of())),
          "me.who_covers_lob.need_lob");
    }

    String lob = intent.coveringLob().strip().toUpperCase(Locale.ROOT);
    List<DirectoryUser> matches = new ArrayList<>();
    for (DirectoryUser user : directory.listDirectoryUsers()) {
      if (user.coveringLobs().stream().anyMatch(item -> lob.equalsIgnoreCase(item))) {
        matches.add(user);
      }
    }
    matches.sort(
        Comparator.comparing(DirectoryUser::familyName)
            .thenComparing(DirectoryUser::givenName)
            .thenComparing(DirectoryUser::userId));

    if (matches.isEmpty()) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WhoCoversLobAnswerView("empty", lob, 0, List.of())),
          "me.who_covers_lob.empty");
    }

    List<WhoCoversLobRow> rows = new ArrayList<>();
    for (DirectoryUser user : matches) {
      String covering =
          user.coveringLobs().isEmpty() ? "—" : String.join(", ", user.coveringLobs());
      rows.add(
          new WhoCoversLobRow(
              user.displayName(),
              user.userId(),
              user.title(),
              identityTokenFormat.formatTokenList(user.roles()),
              covering));
    }
    return new MeIntentResult(
        answerRenderer.render(
            TEMPLATE, new WhoCoversLobAnswerView("ok", lob, matches.size(), rows)),
        "me.who_covers_lob");
  }
}
