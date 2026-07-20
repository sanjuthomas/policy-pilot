package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Directory-level can-I capability answers (parity with Python {@code can_create.py} + handlers). */
@Component
public class CanActOnEntityService {

  private static final String TEMPLATE = "can-act-on-entity";

  private static final Set<String> INSTRUCTION_CREATOR_TITLES =
      Set.of("Analyst", "Associate", "Vice President", "Managing Director");

  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public CanActOnEntityService(
      AnswerRenderer answerRenderer, IdentityTokenFormat identityTokenFormat) {
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public MeIntentResult answer(MeIntent intent, Subject subject) {
    String action = intent.action() == null ? "CREATE" : intent.action();
    String entityType = intent.entityType() == null ? "payment" : intent.entityType();
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);

    if ("CREATE".equals(action)) {
      if ("instruction".equals(entityType)) {
        return canCreateInstruction(subject);
      }
      return canCreatePayment(subject);
    }
    if ("SUBMIT".equals(action)) {
      return canSubmitPayment(subject);
    }
    if ("APPROVE".equals(action) && !StringUtils.hasText(intent.entityId())) {
      return canApprovePayment(subject);
    }
    if (!StringUtils.hasText(intent.entityId())) {
      return render("need_id", subject, null, null, "me.can_act_on_entity.need_id");
    }
    if (!caps.canApprovePayment() && "APPROVE".equals(action)) {
      return render(
          "not_approver", subject, intent.entityId(), null, "me.can_act_on_entity.not_approver");
    }
    return render("pending", subject, intent.entityId(), null, "me.can_act_on_entity.pending");
  }

  MeIntentResult canCreatePayment(Subject subject) {
    boolean hasRole = roles(subject).contains("PAYMENT_CREATOR");
    boolean inMo = groups(subject).contains("MIDDLE_OFFICE");
    List<String> clubs = clubs(subject);
    List<String> covering = covering(subject);

    if (hasRole && inMo && !covering.isEmpty() && !clubs.isEmpty()) {
      return render(
          "create_payment_yes",
          subject,
          null,
          null,
          "me.can_create_payment.yes",
          String.join(", ", covering),
          identityTokenFormat.formatTokenList(clubs),
          List.of(),
          "");
    }

    if (hasRole && StringUtils.hasText(subject.lob()) && !inMo) {
      return render(
          "create_payment_fo_submitter",
          subject,
          null,
          subject.lob(),
          "me.can_create_payment.fo_submitter");
    }

    List<String> gaps = new ArrayList<>();
    if (!hasRole) {
      gaps.add("role `PAYMENT_CREATOR`");
    }
    if (!inMo) {
      gaps.add("group `MIDDLE_OFFICE`");
    }
    if (covering.isEmpty()) {
      gaps.add("covering LOBs");
    }
    if (clubs.isEmpty()) {
      gaps.add("an amount-limit club");
    }
    return render(
        "create_payment_no", subject, null, null, "me.can_create_payment.no", gaps);
  }

  MeIntentResult canCreateInstruction(Subject subject) {
    boolean hasRole = roles(subject).contains("INSTRUCTION_CREATOR");
    boolean inMo = groups(subject).contains("MIDDLE_OFFICE");
    boolean titleOk = INSTRUCTION_CREATOR_TITLES.contains(nullToEmpty(subject.title()));

    if (hasRole && inMo && titleOk) {
      return render(
          "create_instruction_yes", subject, null, null, "me.can_create_instruction.yes");
    }

    List<String> gaps = new ArrayList<>();
    if (!hasRole) {
      gaps.add("role `INSTRUCTION_CREATOR`");
    }
    if (!inMo) {
      gaps.add("group `MIDDLE_OFFICE`");
    }
    if (!titleOk) {
      gaps.add("an eligible creator title (Analyst through Managing Director)");
    }
    String extra = "";
    if (roles(subject).contains("PAYMENT_CREATOR")) {
      extra =
          "\n\nYou do hold `PAYMENT_CREATOR`, which allows **payment** drafts "
              + "(with middle-office / covering LOBs / amount club) — not instruction create.";
    }
    return render(
        "create_instruction_no",
        subject,
        null,
        null,
        "me.can_create_instruction.no",
        null,
        null,
        gaps,
        extra);
  }

  MeIntentResult canSubmitPayment(Subject subject) {
    boolean hasRole = roles(subject).contains("PAYMENT_CREATOR");
    if (hasRole && StringUtils.hasText(subject.lob())) {
      return render(
          "submit_yes", subject, null, subject.lob(), "me.can_submit_payment.yes");
    }
    if (hasRole && groups(subject).contains("MIDDLE_OFFICE")) {
      return render("submit_mo_no_desk", subject, null, null, "me.can_submit_payment.mo_no_desk");
    }
    return render("submit_no", subject, null, null, "me.can_submit_payment.no");
  }

  MeIntentResult canApprovePayment(Subject subject) {
    boolean hasRole = roles(subject).contains("FUNDING_APPROVER");
    boolean inMo = groups(subject).contains("MIDDLE_OFFICE");
    List<String> clubs = clubs(subject);
    List<String> covering = covering(subject);

    if (hasRole && inMo && !covering.isEmpty() && !clubs.isEmpty()) {
      return render(
          "approve_yes",
          subject,
          null,
          null,
          "me.can_approve_payment.yes",
          String.join(", ", covering),
          identityTokenFormat.formatTokenList(clubs),
          List.of(),
          "");
    }

    List<String> gaps = new ArrayList<>();
    if (!hasRole) {
      gaps.add("role `FUNDING_APPROVER`");
    }
    if (!inMo) {
      gaps.add("group `MIDDLE_OFFICE`");
    }
    if (covering.isEmpty()) {
      gaps.add("covering LOBs");
    }
    if (clubs.isEmpty()) {
      gaps.add("an amount-limit club");
    }
    return render("approve_no", subject, null, null, "me.can_approve_payment.no", gaps);
  }

  private MeIntentResult render(
      String variant, Subject subject, String entityId, String deskLob, String intentId) {
    return render(variant, subject, entityId, deskLob, intentId, null, null, List.of(), "");
  }

  private MeIntentResult render(
      String variant,
      Subject subject,
      String entityId,
      String deskLob,
      String intentId,
      List<String> gaps) {
    return render(variant, subject, entityId, deskLob, intentId, null, null, gaps, "");
  }

  private MeIntentResult render(
      String variant,
      Subject subject,
      String entityId,
      String deskLob,
      String intentId,
      String coveringLobs,
      String amountClubs,
      List<String> gaps,
      String extra) {
    CanActOnEntityAnswerView view =
        CanActOnEntityAnswerView.of(
            variant,
            subject.userId(),
            display(subject),
            StringUtils.hasText(subject.title()) ? subject.title() : "—",
            StringUtils.hasText(deskLob)
                ? deskLob
                : (StringUtils.hasText(subject.lob()) ? subject.lob() : "—"),
            coveringLobs == null ? "—" : coveringLobs,
            amountClubs == null ? "—" : amountClubs,
            entityId,
            gaps,
            extra);
    return new MeIntentResult(answerRenderer.render(TEMPLATE, view), intentId);
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

  private static List<String> clubs(Subject subject) {
    return groups(subject).stream().filter(MeAmountClubs::isClub).toList();
  }

  private static String display(Subject subject) {
    if (StringUtils.hasText(subject.familyName()) && StringUtils.hasText(subject.givenName())) {
      return subject.familyName() + ", " + subject.givenName();
    }
    return subject.userId();
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
