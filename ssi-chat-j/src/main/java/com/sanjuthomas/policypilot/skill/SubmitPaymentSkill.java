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

/** Submit-payment skill: PAYMENT_CREATOR + DRAFT → dry-run SUBMIT → confirmation → Go/No Go. */
@Component
public class SubmitPaymentSkill {

  private static final Logger log = LoggerFactory.getLogger(SubmitPaymentSkill.class);
  static final String SKILL = "submit_payment";

  private final EligibilityClient eligibilityClient;
  private final AuthzPaymentEvaluateClient authzClient;
  private final PaymentMutationClient paymentClient;
  private final AuditExecutionClient auditClient;
  private final PendingSkillStore store;

  public SubmitPaymentSkill(
      EligibilityClient eligibilityClient,
      AuthzPaymentEvaluateClient authzClient,
      PaymentMutationClient paymentClient,
      AuditExecutionClient auditClient,
      PendingSkillStore store) {
    this.eligibilityClient = eligibilityClient;
    this.authzClient = authzClient;
    this.paymentClient = paymentClient;
    this.auditClient = auditClient;
    this.store = store;
  }

  public SkillRunResult phase1(String paymentId, Subject subject) {
    List<String> activities = new ArrayList<>();
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    if (!caps.canCreatePayment()) {
      activities.add("Checked role — `" + subject.userId() + "` does not hold `PAYMENT_CREATOR`.");
      PaymentIdSkillFlow.persistForbiddenAudit(
          auditClient,
          SKILL,
          "SUBMIT",
          subject,
          "skill.submit_payment.forbidden",
          "Role gate denied — missing PAYMENT_CREATOR.");
      return SkillRunResult.terminal(
          "**No Go from preflight** — `"
              + subject.userId()
              + "` cannot run the submit-payment skill (needs `PAYMENT_CREATOR`).\n\n"
              + "No payment was submitted.",
          activities,
          "skill.submit_payment.forbidden",
          SKILL);
    }
    return PaymentIdSkillFlow.phase1(
        SKILL,
        "SUBMIT",
        paymentId,
        subject,
        activities,
        eligibilityClient,
        authzClient,
        auditClient,
        store,
        PaymentIdSkillFlow.statusEquals("DRAFT"),
        "Only **DRAFT** payments can be submitted for approval.",
        "Nothing was submitted.",
        "Preflight passed. Review the payment details below, then choose "
            + "**Go** to submit for funding approval or **No Go** to cancel.");
  }

  public SkillRunResult confirm(String pendingId, String decision, Subject subject) {
    return PaymentIdSkillFlow.confirm(
        SKILL,
        "SUBMIT",
        pendingId,
        decision,
        subject,
        authzClient,
        auditClient,
        store,
        "**No Go** — cancelled. Nothing was submitted.",
        "skill.submit_payment.cancelled",
        "Nothing was submitted.",
        new PaymentIdSkillFlow.Mutation() {
          @Override
          public Map<String, Object> mutate(String paymentId, Subject s, String auditExecutionId) {
            return paymentClient.submitPayment(
                paymentId, s.bearerToken(), s.sessionId(), auditExecutionId);
          }

          @Override
          public String successReport(Map<String, Object> payment, PendingSkill pending, Subject s) {
            return SkillFormat.submittedReport(payment, pending.card());
          }

          @Override
          public String successVerb() {
            return "Submitted";
          }

          @Override
          public String successStatus() {
            return "SUBMITTED";
          }
        },
        log);
  }
}
