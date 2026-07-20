package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.ChatUsersDirectory;
import com.sanjuthomas.policypilot.auth.DirectoryUser;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.me.UsersLikeMeAnswerView.MatchRow;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Parity with Python {@code users_like_me.py}. */
@Component
public class UsersLikeMeService {

  private static final String TEMPLATE = "users-like-me";
  private static final int LIMIT = 12;

  private final ChatUsersDirectory directory;
  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public UsersLikeMeService(
      ChatUsersDirectory directory,
      AnswerRenderer answerRenderer,
      IdentityTokenFormat identityTokenFormat) {
    this.directory = directory;
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public MeIntentResult answer(Subject subject) {
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    List<Scored> matches = findMatches(subject);
    String display =
        StringUtils.hasText(subject.familyName()) && StringUtils.hasText(subject.givenName())
            ? subject.familyName() + ", " + subject.givenName()
            : subject.userId();
    String roleBits = identityTokenFormat.formatTokenList(subject.roles(), "none");
    String groupBits = identityTokenFormat.formatTokenList(subject.groups(), "none");
    String lobBits =
        subject.coveringLobs() == null || subject.coveringLobs().isEmpty()
            ? "none"
            : String.join(", ", subject.coveringLobs());

    String header =
        "Users similar to **"
            + display
            + "** (`"
            + subject.userId()
            + "`) — "
            + "roles ["
            + roleBits
            + "], groups ["
            + groupBits
            + "], covering LOBs ["
            + lobBits
            + "].";
    if (!caps.operational() && !caps.compliance()) {
      header += " No operational payment roles were found on your subject.";
    }

    if (matches.isEmpty()) {
      return new MeIntentResult(
          answerRenderer.render(TEMPLATE, new UsersLikeMeAnswerView(header, true, List.of())),
          "me.users_like_me");
    }

    List<MatchRow> rows = new ArrayList<>();
    for (Scored scored : matches) {
      String why =
          scored.reasons().isEmpty() ? "shared attributes" : String.join("; ", scored.reasons());
      rows.add(
          new MatchRow(
              scored.user().displayName(),
              scored.user().userId(),
              scored.user().title(),
              why));
    }
    return new MeIntentResult(
        answerRenderer.render(TEMPLATE, new UsersLikeMeAnswerView(header, false, rows)),
        "me.users_like_me");
  }

  private List<Scored> findMatches(Subject subject) {
    List<Scored> scored = new ArrayList<>();
    for (DirectoryUser user : directory.listDirectoryUsers()) {
      if (user.userId().equals(subject.userId())) {
        continue;
      }
      ScoreResult result = score(subject, user);
      if (result.score() <= 0) {
        continue;
      }
      scored.add(new Scored(user, result.score(), result.reasons()));
    }
    scored.sort(
        Comparator.comparingInt(Scored::score)
            .reversed()
            .thenComparing(s -> s.user().familyName())
            .thenComparing(s -> s.user().givenName()));
    if (scored.size() > LIMIT) {
      return scored.subList(0, LIMIT);
    }
    return scored;
  }

  private static ScoreResult score(Subject subject, DirectoryUser other) {
    List<String> reasons = new ArrayList<>();
    int score = 0;

    Set<String> sharedRoles = new HashSet<>(roles(subject));
    sharedRoles.retainAll(other.roles());
    sharedRoles.retainAll(ChatCapabilities.OPERATIONAL_ROLES);
    if (!sharedRoles.isEmpty()) {
      List<String> sorted = sharedRoles.stream().sorted().toList();
      score += 10 * sorted.size();
      reasons.add("roles " + String.join(", ", sorted));
    }

    List<String> subjectGroups = new ArrayList<>();
    List<String> subjectClubs = new ArrayList<>();
    splitGroups(groups(subject), subjectGroups, subjectClubs);
    List<String> otherGroups = new ArrayList<>();
    List<String> otherClubs = new ArrayList<>();
    splitGroups(other.groups(), otherGroups, otherClubs);

    Set<String> sharedGroups = new HashSet<>(subjectGroups);
    sharedGroups.retainAll(otherGroups);
    if (!sharedGroups.isEmpty()) {
      List<String> sorted = sharedGroups.stream().sorted().toList();
      score += 5 * sorted.size();
      reasons.add("groups " + String.join(", ", sorted));
    }

    Set<String> sharedClubs = new HashSet<>(subjectClubs);
    sharedClubs.retainAll(otherClubs);
    if (!sharedClubs.isEmpty()) {
      List<String> sorted = sharedClubs.stream().sorted().toList();
      score += 4 * sorted.size();
      reasons.add("amount clubs " + String.join(", ", sorted));
    }

    Set<String> sharedLobs = new HashSet<>(covering(subject));
    sharedLobs.retainAll(other.coveringLobs());
    if (!sharedLobs.isEmpty()) {
      List<String> sorted = sharedLobs.stream().sorted().toList();
      score += 3 * sorted.size();
      reasons.add("covering LOBs " + String.join(", ", sorted));
    }

    if (StringUtils.hasText(subject.lob())
        && StringUtils.hasText(other.lob())
        && subject.lob().equals(other.lob())) {
      score += 2;
      reasons.add("desk LOB " + subject.lob());
    }

    if (StringUtils.hasText(subject.title())
        && StringUtils.hasText(other.title())
        && subject.title().equals(other.title())) {
      score += 1;
      reasons.add("title " + subject.title());
    }

    return new ScoreResult(score, reasons);
  }

  private static void splitGroups(
      List<String> groups, List<String> orgOut, List<String> clubsOut) {
    for (String group : groups) {
      if (MeAmountClubs.isClub(group)) {
        clubsOut.add(group);
      } else {
        orgOut.add(group);
      }
    }
  }

  private static List<String> roles(Subject subject) {
    return subject.roles() == null ? List.of() : subject.roles();
  }

  private static List<String> groups(Subject subject) {
    return subject.groups() == null ? List.of() : subject.groups();
  }

  private static List<String> covering(Subject subject) {
    return subject.coveringLobs() == null ? List.of() : subject.coveringLobs();
  }

  private record Scored(DirectoryUser user, int score, List<String> reasons) {}

  private record ScoreResult(int score, List<String> reasons) {}
}
