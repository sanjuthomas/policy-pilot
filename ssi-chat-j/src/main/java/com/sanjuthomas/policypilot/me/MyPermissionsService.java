package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import java.util.ArrayList;
import java.util.List;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Parity with Python {@code answer_my_permissions}. */
@Component
public class MyPermissionsService {

  public static final String INTENT_ID = "me.my_permissions";

  private static final String TEMPLATE = "my-permissions";

  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public MyPermissionsService(
      AnswerRenderer answerRenderer, IdentityTokenFormat identityTokenFormat) {
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public MeIntentResult answer(Subject subject) {
    String display =
        StringUtils.hasText(subject.familyName()) && StringUtils.hasText(subject.givenName())
            ? subject.familyName() + ", " + subject.givenName()
            : subject.userId();

    List<String> orgGroups = new ArrayList<>();
    List<String> clubs = new ArrayList<>();
    for (String group : subject.groups() == null ? List.<String>of() : subject.groups()) {
      if (MeAmountClubs.isClub(group)) {
        clubs.add(group);
      } else {
        orgGroups.add(group);
      }
    }

    String covering =
        subject.coveringLobs() == null || subject.coveringLobs().isEmpty()
            ? "—"
            : String.join(", ", subject.coveringLobs());

    MyPermissionsAnswerView view =
        new MyPermissionsAnswerView(
            display,
            subject.userId(),
            identityTokenFormat.formatTokenList(subject.roles()),
            identityTokenFormat.formatTokenList(orgGroups),
            identityTokenFormat.formatTokenList(clubs),
            covering,
            StringUtils.hasText(subject.lob()) ? subject.lob() : "—",
            capabilityLines(subject));
    return new MeIntentResult(answerRenderer.render(TEMPLATE, view), INTENT_ID);
  }

  List<String> capabilityLines(Subject subject) {
    List<String> roles = subject.roles() == null ? List.of() : subject.roles();
    List<String> groups = subject.groups() == null ? List.of() : subject.groups();
    List<String> clubs = groups.stream().filter(MeAmountClubs::isClub).toList();
    String clubText =
        clubs.isEmpty()
            ? "no amount-limit club"
            : identityTokenFormat.formatTokenList(clubs, "no amount-limit club");
    String covering =
        subject.coveringLobs() == null || subject.coveringLobs().isEmpty()
            ? "no covering LOBs"
            : String.join(", ", subject.coveringLobs());
    String desk = StringUtils.hasText(subject.lob()) ? subject.lob() : "no desk LOB";

    List<String> lines = new ArrayList<>();
    if (roles.contains("FUNDING_APPROVER") && groups.contains("MIDDLE_OFFICE")) {
      lines.add(
          "- **Approve/reject payments** for covering LOBs ("
              + covering
              + ") within "
              + clubText
              + ", subject to four-eyes and reporting-line checks");
    }
    if (roles.contains("PAYMENT_CREATOR") && groups.contains("MIDDLE_OFFICE")) {
      lines.add(
          "- **Create/update/cancel draft payments** for covering LOBs ("
              + covering
              + ") within "
              + clubText);
    }
    if (roles.contains("PAYMENT_CREATOR") && StringUtils.hasText(subject.lob())) {
      lines.add("- **Submit payments** for desk LOB " + desk);
    } else if (roles.contains("PAYMENT_CREATOR")
        && !groups.contains("MIDDLE_OFFICE")
        && !StringUtils.hasText(subject.lob())) {
      lines.add(
          "- **Payment creator role** is present, but middle-office group / desk LOB "
              + "gates may still block create or submit under OPA");
    }
    if (roles.contains("INSTRUCTION_CREATOR") && groups.contains("MIDDLE_OFFICE")) {
      lines.add(
          "- **Create/update/submit/cancel instructions** as middle-office creator "
              + "(title "
              + (StringUtils.hasText(subject.title()) ? subject.title() : "—")
              + ")");
    }
    if (roles.contains("INSTRUCTION_APPROVER") && StringUtils.hasText(subject.lob())) {
      lines.add(
          "- **Approve/reject instructions** for desk LOB "
              + desk
              + " (title "
              + (StringUtils.hasText(subject.title()) ? subject.title() : "—")
              + ")");
    }
    if (roles.contains("COMPLIANCE_ANALYST") || roles.contains("COMPLIANCE_OFFICER")) {
      lines.add(
          "- **Compliance inquiry** — policy summaries, directory, and eligible approvers");
    }
    if (roles.contains("PLATFORM_ADMIN")) {
      lines.add("- **Platform admin** — administer the platform user directory");
    }

    var caps = com.sanjuthomas.policypilot.auth.ChatCapabilities.forSubject(subject);
    if (caps.compliance() || caps.operational()) {
      lines.add(
          "- **Policy Pilot chat** — ask graph/audit questions"
              + (caps.operational() ? " and me-centric permission questions" : ""));
    }

    if (lines.isEmpty()) {
      lines.add(
          "- No payment/instruction capabilities were derived from your roles and groups.");
    }
    return lines;
  }
}
