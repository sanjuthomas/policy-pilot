package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.nullable;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class PaymentIdSkillFlowTest {

  @Mock EligibilityClient eligibilityClient;
  @Mock AuthzPaymentEvaluateClient authzClient;
  @Mock PaymentMutationClient paymentClient;
  @Mock AuditExecutionClient auditClient;

  private PendingSkillStore store;

  private static final String PAYMENT_ID = "20260720-FICC-P-9";

  private static Subject creator() {
    return new Subject(
        "pay-101", "Emily", "Rodriguez", "Analyst", "FICC",
        List.of("PAYMENT_CREATOR"), List.of("MIDDLE_OFFICE"), "sup-1", List.of(), "tok", "sess");
  }

  private static Subject approver() {
    return new Subject(
        "pay-400", "Caroline", "Nguyen", "Approver", "FICC",
        List.of("FUNDING_APPROVER"), List.of("MIDDLE_OFFICE"), "sup-2", List.of("FICC"), "tok", "sess");
  }

  private static Map<String, Object> payment(String status) {
    Map<String, Object> p = new HashMap<>();
    p.put("payment_id", PAYMENT_ID);
    p.put("status", status);
    p.put("instruction_id", "20260720-FICC-I-1");
    p.put("amount", 1_000_000);
    p.put("currency", "USD");
    p.put("owning_lob", "FICC");
    p.put("value_date", "2026-07-21");
    p.put("instruction_version", 2);
    p.put("created_by", Map.of("user_id", "pay-101", "supervisor_id", "sup-1"));
    return p;
  }

  private static Map<String, Object> instruction() {
    return Map.of(
        "instruction_id", "20260720-FICC-I-1",
        "status", "APPROVED",
        "end_date", "2027-07-20",
        "instruction_type", "STANDING",
        "currency", "USD",
        "owning_lob", "FICC");
  }

  private void stubLoad(String paymentStatus, String action, boolean allowed) {
    when(eligibilityClient.getPayment(eq(PAYMENT_ID), anyString(), anyString()))
        .thenReturn(payment(paymentStatus));
    when(eligibilityClient.getInstruction(eq("20260720-FICC-I-1"), anyString(), anyString()))
        .thenReturn(instruction());
    when(authzClient.evaluateExchange(eq(action), any(), anyString(), anyString(), any()))
        .thenReturn(
            new AuthzPaymentEvaluateClient.EvaluateExchange(
                new PolicyDecision(
                    allowed, List.of("basis"), allowed ? List.of() : List.of("nope")),
                Map.of("action", action),
                Map.of("allowed", allowed)));
  }

  @BeforeEach
  void setUp() {
    store = new PendingSkillStore();
  }

  @Test
  void submitPhase1AndConfirmGo() {
    SubmitPaymentSkill skill =
        new SubmitPaymentSkill(eligibilityClient, authzClient, paymentClient, null, store);
    stubLoad("DRAFT", "SUBMIT", true);

    SkillRunResult phase1 = skill.phase1(PAYMENT_ID, creator());
    assertEquals("skill.submit_payment.awaiting_confirmation", phase1.intentId());
    assertTrue(phase1.answer().contains("No Go"));

    when(authzClient.evaluateExchange(eq("SUBMIT"), any(), anyString(), anyString(), any()))
        .thenReturn(
            new AuthzPaymentEvaluateClient.EvaluateExchange(
                new PolicyDecision(true, List.of("basis"), List.of()),
                Map.of("action", "SUBMIT"),
                Map.of("allowed", true)));
    when(paymentClient.submitPayment(
            eq(PAYMENT_ID), anyString(), anyString(), nullable(String.class)))
        .thenReturn(Map.of("payment_id", PAYMENT_ID, "status", "SUBMITTED"));
    SkillRunResult confirm = skill.confirm(phase1.pendingId(), "go", creator());
    assertEquals("skill.submit_payment.submitted", confirm.intentId());
    assertTrue(confirm.answer().contains("submitted for funding approval"));
  }

  @Test
  void submitWrongStatusStops() {
    SubmitPaymentSkill skill =
        new SubmitPaymentSkill(eligibilityClient, authzClient, paymentClient, null, store);
    when(eligibilityClient.getPayment(eq(PAYMENT_ID), anyString(), anyString()))
        .thenReturn(payment("APPROVED"));

    SkillRunResult result = skill.phase1(PAYMENT_ID, creator());
    assertEquals("skill.submit_payment.wrong_status", result.intentId());
  }

  @Test
  void approvePhase1AndConfirmGo() {
    ApprovePaymentSkill skill =
        new ApprovePaymentSkill(eligibilityClient, authzClient, paymentClient, null, store);
    stubLoad("SUBMITTED", "APPROVE", true);

    SkillRunResult phase1 = skill.phase1(PAYMENT_ID, approver());
    assertEquals("skill.approve_payment.awaiting_confirmation", phase1.intentId());

    when(authzClient.evaluateExchange(eq("APPROVE"), any(), anyString(), anyString(), any()))
        .thenReturn(
            new AuthzPaymentEvaluateClient.EvaluateExchange(
                new PolicyDecision(true, List.of("basis"), List.of()),
                Map.of("action", "APPROVE"),
                Map.of("allowed", true)));
    when(paymentClient.approvePayment(
            eq(PAYMENT_ID), anyString(), anyString(), nullable(String.class)))
        .thenReturn(Map.of("payment_id", PAYMENT_ID, "status", "APPROVED"));
    SkillRunResult confirm = skill.confirm(phase1.pendingId(), "go", approver());
    assertEquals("skill.approve_payment.approved", confirm.intentId());
    assertTrue(confirm.answer().contains("Payment approved"));
  }

  @Test
  void cancelPhase1AndConfirmGo() {
    CancelPaymentSkill skill =
        new CancelPaymentSkill(eligibilityClient, authzClient, paymentClient, null, store);
    stubLoad("DRAFT", "CANCEL", true);

    SkillRunResult phase1 = skill.phase1(PAYMENT_ID, creator());
    assertEquals("skill.cancel_payment.awaiting_confirmation", phase1.intentId());

    when(authzClient.evaluateExchange(eq("CANCEL"), any(), anyString(), anyString(), any()))
        .thenReturn(
            new AuthzPaymentEvaluateClient.EvaluateExchange(
                new PolicyDecision(true, List.of("basis"), List.of()),
                Map.of("action", "CANCEL"),
                Map.of("allowed", true)));
    when(paymentClient.cancelPayment(
            eq(PAYMENT_ID), anyString(), anyString(), nullable(String.class)))
        .thenReturn(Map.of("payment_id", PAYMENT_ID, "status", "CANCELLED"));
    SkillRunResult confirm = skill.confirm(phase1.pendingId(), "go", creator());
    assertEquals("skill.cancel_payment.cancelled", confirm.intentId());
    assertTrue(confirm.answer().contains("Payment cancelled"));
  }

  @Test
  void submitDeniedByPolicy() {
    SubmitPaymentSkill skill =
        new SubmitPaymentSkill(eligibilityClient, authzClient, paymentClient, null, store);
    stubLoad("DRAFT", "SUBMIT", false);

    SkillRunResult result = skill.phase1(PAYMENT_ID, creator());
    assertEquals("skill.submit_payment.denied", result.intentId());
  }

  @Test
  void submitPhase1CreatesAuditExecutionAndConfirmPatches() {
    when(auditClient.create(anyMap(), any())).thenReturn("aud-submit-9");
    SubmitPaymentSkill skill =
        new SubmitPaymentSkill(eligibilityClient, authzClient, paymentClient, auditClient, store);
    stubLoad("DRAFT", "SUBMIT", true);

    SkillRunResult phase1 = skill.phase1(PAYMENT_ID, creator());
    assertEquals("skill.submit_payment.awaiting_confirmation", phase1.intentId());
    verify(auditClient).create(anyMap(), any());

    when(authzClient.evaluateExchange(eq("SUBMIT"), any(), anyString(), anyString(), any()))
        .thenReturn(
            new AuthzPaymentEvaluateClient.EvaluateExchange(
                new PolicyDecision(true, List.of("basis"), List.of()),
                Map.of("action", "SUBMIT"),
                Map.of("allowed", true)));
    when(paymentClient.submitPayment(eq(PAYMENT_ID), anyString(), anyString(), eq("aud-submit-9")))
        .thenReturn(Map.of("payment_id", PAYMENT_ID, "status", "SUBMITTED"));

    SkillRunResult confirm = skill.confirm(phase1.pendingId(), "go", creator());
    assertEquals("skill.submit_payment.submitted", confirm.intentId());
    verify(auditClient).patch(eq("aud-submit-9"), anyMap(), any());
  }

  @Test
  void submitNoGoPatchesAuditCancelled() {
    when(auditClient.create(anyMap(), any())).thenReturn("aud-cancel-go");
    SubmitPaymentSkill skill =
        new SubmitPaymentSkill(eligibilityClient, authzClient, paymentClient, auditClient, store);
    stubLoad("DRAFT", "SUBMIT", true);

    SkillRunResult phase1 = skill.phase1(PAYMENT_ID, creator());
    SkillRunResult confirm = skill.confirm(phase1.pendingId(), "no_go", creator());
    assertEquals("skill.submit_payment.cancelled", confirm.intentId());
    verify(auditClient).patch(eq("aud-cancel-go"), anyMap(), any());
  }

  @Test
  void submitForbiddenPersistsTerminalAudit() {
    Subject noCreator =
        new Subject(
            "pay-999",
            "No",
            "Creator",
            "Analyst",
            "FICC",
            List.of("FUNDING_APPROVER"),
            List.of("MIDDLE_OFFICE"),
            "sup-1",
            List.of(),
            "tok",
            "sess");
    SubmitPaymentSkill skill =
        new SubmitPaymentSkill(eligibilityClient, authzClient, paymentClient, auditClient, store);

    SkillRunResult result = skill.phase1(PAYMENT_ID, noCreator);
    assertEquals("skill.submit_payment.forbidden", result.intentId());
    verify(auditClient).create(anyMap(), any());
  }

  @Test
  void capabilityForMapsPaymentSkills() {
    assertEquals("SUBMIT_PAYMENT", PaymentIdSkillFlow.capabilityFor("submit_payment"));
    assertEquals("APPROVE_PAYMENT", PaymentIdSkillFlow.capabilityFor("approve_payment"));
    assertEquals("CANCEL_PAYMENT", PaymentIdSkillFlow.capabilityFor("cancel_payment"));
    assertEquals("CREATE_PAYMENT", PaymentIdSkillFlow.capabilityFor("create_payment"));
  }

  @Test
  void resultWithPaymentIdCopiesFromRequestWhenMissing() {
    Map<String, Object> out =
        PaymentIdSkillFlow.resultWithPaymentId(
            Map.of("payment_id", PAYMENT_ID),
            Map.of("message", "APPROVE denied", "violations", List.of("SELF_APPROVAL")));
    assertEquals(PAYMENT_ID, out.get("payment_id"));
    assertEquals("APPROVE denied", out.get("message"));
  }
}
