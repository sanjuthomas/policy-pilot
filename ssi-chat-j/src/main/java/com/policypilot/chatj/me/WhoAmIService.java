package com.policypilot.chatj.me;

import com.policypilot.chatj.auth.ChatCapabilities;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.IdentityTokenFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Who-am-I answer from the logged-in subject — parity with Python {@code answer_who_am_i}. */
@Component
public class WhoAmIService {

  public static final String INTENT_ID = "me.who_am_i";

  private static final String TEMPLATE = "who-am-i";

  private static final Set<String> AMOUNT_CLUBS =
      Set.of("UP_TO_100_MILLION_CLUB", "UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB");

  private final AnswerRenderer answerRenderer;
  private final IdentityTokenFormat identityTokenFormat;

  public WhoAmIService(AnswerRenderer answerRenderer, IdentityTokenFormat identityTokenFormat) {
    this.answerRenderer = answerRenderer;
    this.identityTokenFormat = identityTokenFormat;
  }

  public String answer(Subject subject) {
    return answerRenderer.render(TEMPLATE, toView(subject));
  }

  WhoAmIAnswerView toView(Subject subject) {
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    String display =
        StringUtils.hasText(subject.familyName()) && StringUtils.hasText(subject.givenName())
            ? subject.familyName() + ", " + subject.givenName()
            : subject.userId();

    List<String> orgGroups = new ArrayList<>();
    List<String> clubs = new ArrayList<>();
    for (String group : subject.groups() == null ? List.<String>of() : subject.groups()) {
      if (AMOUNT_CLUBS.contains(group)) {
        clubs.add(group);
      } else {
        orgGroups.add(group);
      }
    }

    List<String> audienceBits = new ArrayList<>();
    if (caps.compliance()) {
      audienceBits.add("compliance inquiry");
    }
    if (caps.canCreatePayment()) {
      audienceBits.add("payment creator");
    }
    if (caps.canCancelPayment()) {
      audienceBits.add("payment canceller");
    }
    if (caps.canApprovePayment()) {
      audienceBits.add("funding approver");
    }
    String audience = audienceBits.isEmpty() ? "chat user" : String.join(", ", audienceBits);

    String covering =
        subject.coveringLobs() == null || subject.coveringLobs().isEmpty()
            ? "—"
            : String.join(", ", subject.coveringLobs());

    return new WhoAmIAnswerView(
        display,
        subject.userId(),
        StringUtils.hasText(subject.title()) ? subject.title() : "—",
        identityTokenFormat.formatTokenList(subject.roles()),
        identityTokenFormat.formatTokenList(orgGroups),
        identityTokenFormat.formatTokenList(clubs),
        StringUtils.hasText(subject.lob()) ? subject.lob() : "—",
        covering,
        StringUtils.hasText(subject.supervisorId()) ? subject.supervisorId() : "—",
        audience);
  }
}
