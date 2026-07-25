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

/** Approve-payment skill: FUNDING_APPROVER + SUBMITTED → dry-run APPROVE → confirmation → Go/No Go. */
@Component
public class ApprovePaymentSkill {

  private static final Logger log = LoggerFactory.getLogger(ApprovePaymentSkill.class);
  static final String SKILL = "approve_payment";

  private final EligibilityClient eligibilityClient;
  private final AuthzPaymentEvaluateClient authzClient;
  private final PaymentMutationClient paymentClient;
  private final AuditExecutionClient auditClient;
  private final PendingSkillStore store;

  public ApprovePaymentSkill(
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
    if (!caps.canApprovePayment()) {
      activities.add("Checked role — `" + subject.userId() + "` does not hold `FUNDING_APPROVER`.");
      PaymentIdSkillFlow.persistForbiddenAudit(
          auditClient,
          SKILL,
          "APPROVE",
          subject,
          "skill.approve_payment.forbidden",
          "Role gate denied — missing FUNDING_APPROVER.");
      return SkillRunResult.terminal(
          "**No Go from preflight** — `"
              + subject.userId()
              + "` cannot run the approve-payment skill (needs `FUNDING_APPROVER`).\n\n"
              + "No payment was approved.",
          activities,
          "skill.approve_payment.forbidden",
          SKILL);
    }
    return PaymentIdSkillFlow.phase1(
        SKILL,
        "APPROVE",
        paymentId,
        subject,
        activities,
        eligibilityClient,
        authzClient,
        auditClient,
        store,
        PaymentIdSkillFlow.statusEquals("SUBMITTED"),
        "Only **SUBMITTED** payments can be funding-approved.",
        "Nothing was approved.",
        "Preflight passed. Review the payment details below, then choose "
            + "**Go** to funding-approve or **No Go** to cancel.");
  }

  public SkillRunResult confirm(String pendingId, String decision, Subject subject) {
    return PaymentIdSkillFlow.confirm(
        SKILL,
        "APPROVE",
        pendingId,
        decision,
        subject,
        authzClient,
        auditClient,
        store,
        "**No Go** — cancelled. Nothing was approved.",
        "skill.approve_payment.cancelled",
        "Nothing was approved.",
        new PaymentIdSkillFlow.Mutation() {
          @Override
          public Map<String, Object> mutate(String paymentId, Subject s, String auditExecutionId) {
            return paymentClient.approvePayment(
                paymentId, s.bearerToken(), s.sessionId(), auditExecutionId);
          }

          @Override
          public String successReport(Map<String, Object> payment, PendingSkill pending, Subject s) {
            return SkillFormat.approvedReport(payment, pending.card(), SkillFormat.displayName(s));
          }

          @Override
          public String successVerb() {
            return "Approved";
          }

          @Override
          public String successStatus() {
            return "APPROVED";
          }
        },
        log);
  }
}
