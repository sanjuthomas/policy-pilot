package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Cancel-payment skill: PAYMENT_CREATOR + MIDDLE_OFFICE, DRAFT|SUBMITTED → dry-run CANCEL →
 * confirmation → Go/No Go. Note: No Go uses intent {@code skill.cancel_payment.no_go}.
 */
@Component
public class CancelPaymentSkill {

  private static final Logger log = LoggerFactory.getLogger(CancelPaymentSkill.class);
  static final String SKILL = "cancel_payment";

  private final EligibilityClient eligibilityClient;
  private final AuthzPaymentEvaluateClient authzClient;
  private final PaymentMutationClient paymentClient;
  private final PendingSkillStore store;

  public CancelPaymentSkill(
      EligibilityClient eligibilityClient,
      AuthzPaymentEvaluateClient authzClient,
      PaymentMutationClient paymentClient,
      PendingSkillStore store) {
    this.eligibilityClient = eligibilityClient;
    this.authzClient = authzClient;
    this.paymentClient = paymentClient;
    this.store = store;
  }

  public SkillRunResult phase1(String paymentId, Subject subject) {
    List<String> activities = new ArrayList<>();
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    if (!caps.canCancelPayment()) {
      activities.add(
          "Checked role/group — `"
              + subject.userId()
              + "` cannot cancel payments (needs `PAYMENT_CREATOR` + `MIDDLE_OFFICE`).");
      return SkillRunResult.terminal(
          "**No Go from preflight** — `"
              + subject.userId()
              + "` cannot run the cancel-payment skill (needs `PAYMENT_CREATOR` and "
              + "`MIDDLE_OFFICE`).\n\nNo payment was cancelled.",
          activities,
          "skill.cancel_payment.forbidden",
          SKILL);
    }
    return PaymentIdSkillFlow.phase1(
        SKILL,
        "CANCEL",
        paymentId,
        subject,
        activities,
        eligibilityClient,
        authzClient,
        store,
        PaymentIdSkillFlow.statusIn("DRAFT", "SUBMITTED"),
        "Only **DRAFT** or **SUBMITTED** payments can be cancelled.",
        "Nothing was cancelled.",
        "Preflight passed. Review the payment details below, then choose "
            + "**Go** to cancel the payment or **No Go** to keep it.");
  }

  public SkillRunResult confirm(String pendingId, String decision, Subject subject) {
    return PaymentIdSkillFlow.confirm(
        SKILL,
        "CANCEL",
        pendingId,
        decision,
        subject,
        authzClient,
        store,
        "**No Go** — cancelled. Nothing was changed on the payment.",
        "skill.cancel_payment.no_go",
        "Nothing was cancelled.",
        new PaymentIdSkillFlow.Mutation() {
          @Override
          public Map<String, Object> mutate(String paymentId, Subject s) {
            return paymentClient.cancelPayment(paymentId, s.bearerToken(), s.sessionId());
          }

          @Override
          public String successReport(Map<String, Object> payment, PendingSkill pending, Subject s) {
            return SkillFormat.cancelledReport(payment, pending.card(), SkillFormat.displayName(s));
          }

          @Override
          public String successVerb() {
            return "Cancelled";
          }

          @Override
          public String successStatus() {
            return "CANCELLED";
          }
        },
        log);
  }
}
