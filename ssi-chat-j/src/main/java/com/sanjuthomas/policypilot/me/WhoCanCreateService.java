package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.auth.ChatUsersDirectory;
import com.sanjuthomas.policypilot.auth.DirectoryUser;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.me.WhoCanCreateAnswerView.CreatorRow;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Parity with Python {@code who_can_create.py}. */
@Component
public class WhoCanCreateService {

  private static final String TEMPLATE = "who-can-create";

  private final ChatUsersDirectory directory;
  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public WhoCanCreateService(
      ChatUsersDirectory directory,
      AnswerRenderer answerRenderer,
      IdentityTokenFormat identityTokenFormat) {
    this.directory = directory;
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public MeIntentResult answer(MeIntent intent, Subject subject) {
    if ("instruction".equalsIgnoreCase(nullToEmpty(intent.entityType()))) {
      return forInstruction(intent.coveringLob(), subject);
    }
    return forPayment(intent.coveringLob(), subject);
  }

  MeIntentResult forPayment(String coveringLob, Subject subject) {
    String lobLabel =
        StringUtils.hasText(coveringLob) ? coveringLob.strip().toUpperCase(Locale.ROOT) : null;
    List<DirectoryUser> creators = paymentCreators(lobLabel);
    if (creators.isEmpty()) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WhoCanCreateAnswerView("payment_empty", lobLabel, List.of())),
          "me.who_can_create.payment.empty");
    }

    List<CreatorRow> rows = new ArrayList<>();
    for (DirectoryUser user : creators) {
      List<String> clubs = user.groups().stream().filter(MeAmountClubs::isClub).toList();
      List<String> org = user.groups().stream().filter(g -> !MeAmountClubs.isClub(g)).toList();
      String covering =
          user.coveringLobs().isEmpty() ? "—" : String.join(", ", user.coveringLobs());
      rows.add(
          new CreatorRow(
              user.displayName(),
              user.userId(),
              user.title(),
              covering,
              identityTokenFormat.formatTokenList(clubs),
              identityTokenFormat.formatTokenList(org),
              null,
              subject != null && user.userId().equals(subject.userId())));
    }
    return new MeIntentResult(
        answerRenderer.render(
            TEMPLATE, new WhoCanCreateAnswerView("payment_ok", lobLabel, rows)),
        "me.who_can_create.payment");
  }

  MeIntentResult forInstruction(String coveringLob, Subject subject) {
    List<DirectoryUser> creators = instructionCreators();
    String lobLabel =
        StringUtils.hasText(coveringLob) ? coveringLob.strip().toUpperCase(Locale.ROOT) : null;
    if (creators.isEmpty()) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WhoCanCreateAnswerView("instruction_empty", lobLabel, List.of())),
          "me.who_can_create.instruction.empty");
    }

    List<CreatorRow> rows = new ArrayList<>();
    for (DirectoryUser user : creators) {
      String supervisor =
          StringUtils.hasText(user.supervisorId()) ? user.supervisorId() : "—";
      rows.add(
          new CreatorRow(
              user.displayName(),
              user.userId(),
              user.title(),
              null,
              null,
              null,
              supervisor,
              subject != null && user.userId().equals(subject.userId())));
    }
    return new MeIntentResult(
        answerRenderer.render(
            TEMPLATE, new WhoCanCreateAnswerView("instruction_ok", lobLabel, rows)),
        "me.who_can_create.instruction");
  }

  private List<DirectoryUser> paymentCreators(String lobUpperOrNull) {
    List<DirectoryUser> matches = new ArrayList<>();
    for (DirectoryUser user : directory.listDirectoryUsers()) {
      if (!user.roles().contains("PAYMENT_CREATOR")) {
        continue;
      }
      if (!user.groups().contains("MIDDLE_OFFICE")) {
        continue;
      }
      if (lobUpperOrNull != null) {
        boolean covers =
            user.coveringLobs().stream()
                .anyMatch(lob -> lobUpperOrNull.equalsIgnoreCase(lob));
        if (!covers) {
          continue;
        }
      }
      matches.add(user);
    }
    matches.sort(
        Comparator.comparing(DirectoryUser::familyName)
            .thenComparing(DirectoryUser::givenName)
            .thenComparing(DirectoryUser::userId));
    return matches;
  }

  private List<DirectoryUser> instructionCreators() {
    List<DirectoryUser> matches = new ArrayList<>();
    for (DirectoryUser user : directory.listDirectoryUsers()) {
      if (!user.roles().contains("INSTRUCTION_CREATOR")) {
        continue;
      }
      if (!user.groups().contains("MIDDLE_OFFICE")) {
        continue;
      }
      matches.add(user);
    }
    matches.sort(
        Comparator.comparing(DirectoryUser::familyName)
            .thenComparing(DirectoryUser::givenName)
            .thenComparing(DirectoryUser::userId));
    return matches;
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
