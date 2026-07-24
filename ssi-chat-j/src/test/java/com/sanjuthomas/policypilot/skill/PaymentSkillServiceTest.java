package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.FakeEligibilityClient;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import org.junit.jupiter.api.Test;

class PaymentSkillServiceTest {

  private PendingSkillStore store;

  private PaymentSkillService service() {
    store = new PendingSkillStore();
    FakeEligibilityClient client = new FakeEligibilityClient();
    return new PaymentSkillService(
        new CreatePaymentSkill(client, null, null, store),
        new SubmitPaymentSkill(client, null, null, store),
        new ApprovePaymentSkill(client, null, null, store),
        new CancelPaymentSkill(client, null, null, store));
  }

  private static RouterDecision skill(String skill) {
    RouterDecision decision = new RouterDecision();
    decision.setPath("skill");
    decision.setSkill(skill);
    return decision;
  }

  private static Subject subject(String userId, List<String> roles, List<String> groups) {
    return new Subject(
        userId, "Given", "Family", "Analyst", "FICC", roles, groups, "sup-1", List.of(), "tok", "sess");
  }

  private static Subject paymentCreator() {
    return subject("pay-101", List.of("PAYMENT_CREATOR"), List.of());
  }

  private static Subject fundingApprover() {
    return subject("pay-400", List.of("FUNDING_APPROVER"), List.of());
  }

  @Test
  void wrongModeReturnsPaymentsHint() {
    SkillRunResult result =
        service().phase1(skill("create_payment"), "please create a payment", "events", paymentCreator());
    assertEquals("gate.skill_wrong_mode", result.intentId());
    assertTrue(result.answer().contains("Payments"));
  }

  @Test
  void nonOperationalUserBlockedByFence() {
    Subject compliance = subject("comp-001", List.of("COMPLIANCE_ANALYST"), List.of());
    SkillRunResult result =
        service().phase1(skill("create_payment"), "please create a payment", "payments", compliance);
    assertEquals("gate.skill_not_creator", result.intentId());
  }

  @Test
  void createForbiddenForFundingApproverOnly() {
    SkillRunResult result =
        service()
            .phase1(
                skill("create_payment"),
                "create a payment for instruction 20260720-FICC-I-1 amount 1m value date tomorrow",
                "payments",
                fundingApprover());
    assertEquals("skill.create_payment.forbidden", result.intentId());
    assertTrue(result.answer().contains("cannot run the create-payment skill"));
    assertTrue(result.answer().contains("PAYMENT_CREATOR"));
    assertTrue(result.answer().contains("No payment was created"));
  }

  @Test
  void submitForbiddenForFundingApproverOnly() {
    SkillRunResult result =
        service()
            .phase1(
                skill("submit_payment"),
                "please submit payment 20260720-FICC-P-9 for approval",
                "payments",
                fundingApprover());
    assertEquals("skill.submit_payment.forbidden", result.intentId());
    assertTrue(result.answer().contains("cannot run the submit-payment skill"));
    assertTrue(result.answer().contains("No payment was submitted"));
  }

  @Test
  void approveForbiddenForPaymentCreatorOnly() {
    SkillRunResult result =
        service()
            .phase1(
                skill("approve_payment"),
                "please approve payment 20260720-FICC-P-9",
                "payments",
                paymentCreator());
    assertEquals("skill.approve_payment.forbidden", result.intentId());
    assertTrue(result.answer().contains("cannot run the approve-payment skill"));
    assertTrue(result.answer().contains("FUNDING_APPROVER"));
    assertTrue(result.answer().contains("No payment was approved"));
  }

  @Test
  void cancelForbiddenWithoutMiddleOffice() {
    SkillRunResult result =
        service()
            .phase1(
                skill("cancel_payment"),
                "please cancel payment 20260720-FICC-P-9",
                "payments",
                paymentCreator());
    assertEquals("skill.cancel_payment.forbidden", result.intentId());
    assertTrue(result.answer().contains("cannot run the cancel-payment skill"));
    assertTrue(result.answer().contains("MIDDLE_OFFICE"));
    assertTrue(result.answer().contains("No payment was cancelled"));
  }

  @Test
  void createIncompleteWhenSlotsMissing() {
    SkillRunResult result =
        service().phase1(skill("create_payment"), "please create a payment", "payments", paymentCreator());
    assertEquals("skill.create_payment.incomplete", result.intentId());
  }

  @Test
  void submitIncompleteWhenPaymentIdMissing() {
    SkillRunResult result =
        service().phase1(skill("submit_payment"), "please submit the payment", "payments", paymentCreator());
    assertEquals("skill.submit_payment.incomplete", result.intentId());
  }

  @Test
  void blankSkillDefaultsToCreate() {
    SkillRunResult result =
        service().phase1(skill(null), "please create a payment", "payments", paymentCreator());
    assertEquals("skill.create_payment.incomplete", result.intentId());
    assertEquals("create_payment", result.skill());
  }

  @Test
  void confirmNoGoCreateDiscardsPending() {
    PaymentSkillService svc = service();
    String pendingId = plantCreatePending("pay-101");
    SkillRunResult result = svc.confirm("create_payment", pendingId, "no_go", paymentCreator());
    assertEquals("skill.create_payment.cancelled", result.intentId());
    assertTrue(result.answer().contains("No Go"));
  }

  @Test
  void confirmNoGoCancelUsesNoGoIntent() {
    PaymentSkillService svc = service();
    String pendingId = plantCancelPending("pay-101");
    SkillRunResult result =
        svc.confirm(
            "cancel_payment",
            pendingId,
            "no_go",
            subject("pay-101", List.of("PAYMENT_CREATOR"), List.of("MIDDLE_OFFICE")));
    assertEquals("skill.cancel_payment.no_go", result.intentId());
    assertTrue(result.answer().contains("No Go"));
    assertTrue(result.answer().contains("Nothing was changed"));
  }

  @Test
  void confirmUnknownPendingReturnsMissing() {
    SkillRunResult result = service().confirm("create_payment", "nope", "no_go", paymentCreator());
    assertEquals("skill.create_payment.pending_missing", result.intentId());
  }

  @Test
  void confirmCrossUserForbidden() {
    PaymentSkillService svc = service();
    String pendingId = plantCreatePending("someone-else");
    SkillRunResult result = svc.confirm("create_payment", pendingId, "no_go", paymentCreator());
    assertEquals("skill.create_payment.pending_forbidden", result.intentId());
  }

  @Test
  void confirmBadDecisionRejected() {
    PaymentSkillService svc = service();
    String pendingId = plantCreatePending("pay-101");
    SkillRunResult result = svc.confirm("create_payment", pendingId, "maybe", paymentCreator());
    assertEquals("skill.create_payment.bad_decision", result.intentId());
  }

  private String plantCreatePending(String userId) {
    String id = store.newPendingId();
    store.put(
        new PendingSkill(
            id,
            "create_payment",
            userId,
            null,
            "20260720-FICC-I-1",
            1_000_000d,
            "2026-07-21",
            "USD",
            "FICC",
            null,
            "APPROVED",
            "2027-07-20",
            "STANDING",
            1,
            null,
            null,
            card(null, null),
            store.defaultExpiresAt()));
    return id;
  }

  private String plantCancelPending(String userId) {
    String id = store.newPendingId();
    store.put(
        new PendingSkill(
            id,
            "cancel_payment",
            userId,
            "20260720-FICC-P-9",
            "20260720-FICC-I-1",
            1_000_000d,
            "2026-07-21",
            "USD",
            "FICC",
            "DRAFT",
            "APPROVED",
            "2027-07-20",
            "STANDING",
            1,
            "pay-101",
            "sup-1",
            card("20260720-FICC-P-9", "DRAFT"),
            store.defaultExpiresAt()));
    return id;
  }

  private static ConfirmationCard card(String paymentId, String paymentStatus) {
    return new ConfirmationCard(
        "20260720-FICC-I-1",
        1_000_000d,
        "USD",
        "2026-07-21",
        "FICC",
        "APPROVED",
        null,
        null,
        null,
        null,
        List.of(),
        paymentId,
        paymentStatus);
  }
}
