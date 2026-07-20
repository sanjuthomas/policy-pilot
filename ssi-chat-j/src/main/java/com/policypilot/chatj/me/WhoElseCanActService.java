package com.policypilot.chatj.me;

import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.eligibility.EligibilityClient;
import com.policypilot.chatj.eligibility.EligibilityPayloads;
import com.policypilot.chatj.eligibility.EligiblePaymentApproversView.ApproverRow;
import com.policypilot.chatj.formatting.AnswerRenderer;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

/** Live who-else-can-approve: eligible-approvers minus the caller. */
@Component
public class WhoElseCanActService {

  private static final String TEMPLATE = "who-else-can-act";

  private final EligibilityClient eligibilityClient;
  private final AnswerRenderer answerRenderer;

  public WhoElseCanActService(
      EligibilityClient eligibilityClient, AnswerRenderer answerRenderer) {
    this.eligibilityClient = eligibilityClient;
    this.answerRenderer = answerRenderer;
  }

  public MeIntentResult answer(MeIntent intent, Subject subject) {
    if (!StringUtils.hasText(intent.entityId())) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WhoElseCanActAnswerView("need_id", null, null, List.of())),
          "me.who_else_can_act.need_id");
    }

    String paymentId = intent.entityId().strip();
    try {
      Map<String, Object> data =
          eligibilityClient.eligibleApproversForPayment(
              paymentId, subject.bearerToken(), subject.sessionId());
      String blocked = EligibilityPayloads.blockedOrNull(data.get("approval_blocked_reason"));
      if (blocked != null) {
        return new MeIntentResult(
            answerRenderer.render(
                TEMPLATE, new WhoElseCanActAnswerView("blocked", paymentId, blocked, List.of())),
            "me.who_else_can_act.blocked");
      }

      List<ApproverRow> others =
          EligibilityPayloads.toApproverRows(data.get("eligible")).stream()
              .filter(row -> row.userId() != null && !row.userId().equals(subject.userId()))
              .toList();
      if (others.isEmpty()) {
        return new MeIntentResult(
            answerRenderer.render(
                TEMPLATE, new WhoElseCanActAnswerView("empty", paymentId, null, List.of())),
            "me.who_else_can_act.empty");
      }
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WhoElseCanActAnswerView("found", paymentId, null, others)),
          "me.who_else_can_act.found");
    } catch (ResponseStatusException ex) {
      if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
        return new MeIntentResult(
            "Payment `" + paymentId + "` was not found.",
            "me.who_else_can_act.not_found");
      }
      throw ex;
    }
  }
}
