package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.eligibility.EligibilityPayloads;
import com.sanjuthomas.policypilot.eligibility.EligiblePaymentApproversView.ApproverRow;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.me.WaitingForMeAnswerView.WorklistItem;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * Approver worklist: SUBMITTED payments where live OPA eligible-approvers includes the caller.
 *
 * <p>Demo-scale: list + per-payment eligible-approvers (N+1). A dedicated authz worklist can replace
 * this later.
 */
@Component
public class WaitingForMeService {

  private static final Logger log = LoggerFactory.getLogger(WaitingForMeService.class);
  private static final String TEMPLATE = "waiting-for-me";
  private static final int LIST_LIMIT = 100;
  private static final int MAX_CHECKS = 40;

  private final EligibilityClient eligibilityClient;
  private final AnswerRenderer answerRenderer;

  public WaitingForMeService(
      EligibilityClient eligibilityClient, AnswerRenderer answerRenderer) {
    this.eligibilityClient = eligibilityClient;
    this.answerRenderer = answerRenderer;
  }

  public MeIntentResult answer(Subject subject) {
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    if (!caps.canApprovePayment()) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WaitingForMeAnswerView("not_approver", subject.userId(), List.of())),
          "me.waiting_for_me.not_approver");
    }

    List<Map<String, Object>> submitted =
        eligibilityClient.listPayments(
            "SUBMITTED", LIST_LIMIT, subject.bearerToken(), subject.sessionId());

    List<WorklistItem> items = new ArrayList<>();
    int checked = 0;
    for (Map<String, Object> payment : submitted) {
      if (checked >= MAX_CHECKS) {
        break;
      }
      String paymentId = EligibilityPayloads.str(payment.get("payment_id"));
      if (!StringUtils.hasText(paymentId)) {
        continue;
      }
      checked++;
      try {
        Map<String, Object> data =
            eligibilityClient.eligibleApproversForPayment(
                paymentId, subject.bearerToken(), subject.sessionId());
        if (EligibilityPayloads.blockedOrNull(data.get("approval_blocked_reason")) != null) {
          continue;
        }
        boolean me =
            EligibilityPayloads.toApproverRows(data.get("eligible")).stream()
                .map(ApproverRow::userId)
                .anyMatch(id -> subject.userId().equals(id));
        if (!me) {
          continue;
        }
        items.add(
            new WorklistItem(
                paymentId,
                payment.get("amount"),
                EligibilityPayloads.blankToNull(EligibilityPayloads.str(payment.get("currency"))),
                EligibilityPayloads.blankToNull(EligibilityPayloads.str(payment.get("owning_lob"))),
                EligibilityPayloads.blankToNull(
                    EligibilityPayloads.str(payment.get("instruction_id")))));
      } catch (RuntimeException ex) {
        log.debug("skip payment {} for waiting_for_me: {}", paymentId, ex.toString());
      }
    }

    if (items.isEmpty()) {
      return new MeIntentResult(
          answerRenderer.render(
              TEMPLATE, new WaitingForMeAnswerView("empty", subject.userId(), List.of())),
          "me.waiting_for_me.empty");
    }
    return new MeIntentResult(
        answerRenderer.render(
            TEMPLATE, new WaitingForMeAnswerView("found", subject.userId(), items)),
        "me.waiting_for_me.found");
  }
}
