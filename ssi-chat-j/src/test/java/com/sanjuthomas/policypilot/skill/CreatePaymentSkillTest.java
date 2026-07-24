package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import com.sanjuthomas.policypilot.skill.SkillParamParser.CreateParams;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@ExtendWith(MockitoExtension.class)
class CreatePaymentSkillTest {

  @Mock EligibilityClient eligibilityClient;
  @Mock AuthzPaymentEvaluateClient authzClient;
  @Mock PaymentMutationClient paymentClient;

  private PendingSkillStore store;
  private CreatePaymentSkill skill;

  private static Subject creator() {
    return new Subject(
        "pay-101", "Emily", "Rodriguez", "Analyst", "FICC",
        List.of("PAYMENT_CREATOR"), List.of("MIDDLE_OFFICE"), "sup-1", List.of(), "tok", "sess");
  }

  private static Map<String, Object> instruction() {
    return Map.of(
        "instruction_id", "20260720-FICC-I-1",
        "owning_lob", "FICC",
        "currency", "USD",
        "status", "APPROVED",
        "end_date", "2027-07-20",
        "instruction_type", "STANDING",
        "version_number", 2);
  }

  @BeforeEach
  void setUp() {
    store = new PendingSkillStore();
    skill = new CreatePaymentSkill(eligibilityClient, authzClient, paymentClient, store);
  }

  @Test
  void phase1AwaitsConfirmationWhenAllowed() {
    when(eligibilityClient.getInstruction(eq("20260720-FICC-I-1"), anyString(), anyString()))
        .thenReturn(instruction());
    when(authzClient.evaluate(eq("CREATE"), any(), anyString(), anyString(), any()))
        .thenReturn(new PolicyDecision(true, List.of("role PAYMENT_CREATOR"), List.of()));

    SkillRunResult result =
        skill.phase1(new CreateParams("20260720-FICC-I-1", 1_000_000d, "2026-07-21"), creator());

    assertEquals("skill.create_payment.awaiting_confirmation", result.intentId());
    assertTrue(result.hasConfirmation());
    assertTrue(result.answer().contains("Preflight"));
    assertTrue(result.answer().contains("Go"));
  }

  @Test
  void phase1StopsWhenInstructionMissing() {
    when(eligibilityClient.getInstruction(anyString(), anyString(), anyString()))
        .thenThrow(new ResponseStatusException(HttpStatus.NOT_FOUND, "missing"));

    SkillRunResult result =
        skill.phase1(new CreateParams("20260720-FICC-I-9", 1_000_000d, "2026-07-21"), creator());

    assertEquals("skill.create_payment.instruction_missing", result.intentId());
  }

  @Test
  void phase1StopsWhenInstructionForbidden() {
    when(eligibilityClient.getInstruction(anyString(), anyString(), anyString()))
        .thenThrow(new ResponseStatusException(HttpStatus.FORBIDDEN, "covering miss"));

    SkillRunResult result =
        skill.phase1(new CreateParams("20260720-FICC-I-1", 1_000_000d, "2026-07-21"), creator());

    assertEquals("skill.create_payment.instruction_forbidden", result.intentId());
    assertTrue(result.answer().contains("No payment was created"));
    assertTrue(result.answer().toLowerCase().contains("not authorized"));
  }

  @Test
  void phase1DeniedWhenPolicyRejects() {
    when(eligibilityClient.getInstruction(anyString(), anyString(), anyString()))
        .thenReturn(instruction());
    when(authzClient.evaluate(eq("CREATE"), any(), anyString(), anyString(), any()))
        .thenReturn(new PolicyDecision(false, List.of(), List.of("four-eyes")));

    SkillRunResult result =
        skill.phase1(new CreateParams("20260720-FICC-I-1", 1_000_000d, "2026-07-21"), creator());

    assertEquals("skill.create_payment.denied", result.intentId());
  }

  @Test
  void confirmGoCreatesDraftPayment() {
    when(eligibilityClient.getInstruction(anyString(), anyString(), anyString()))
        .thenReturn(instruction());
    when(authzClient.evaluate(eq("CREATE"), any(), anyString(), anyString(), any()))
        .thenReturn(new PolicyDecision(true, List.of("role PAYMENT_CREATOR"), List.of()));
    SkillRunResult phase1 =
        skill.phase1(new CreateParams("20260720-FICC-I-1", 1_000_000d, "2026-07-21"), creator());

    when(paymentClient.createPayment(anyString(), any(Double.class), anyString(), anyString(), anyString()))
        .thenReturn(Map.of("payment_id", "20260720-FICC-P-9", "status", "DRAFT"));

    SkillRunResult result = skill.confirm(phase1.pendingId(), "go", creator());

    assertEquals("skill.create_payment.created", result.intentId());
    assertTrue(result.answer().contains("Payment created"));
  }

  @Test
  void confirmGoStopsWhenRecheckDenies() {
    when(eligibilityClient.getInstruction(anyString(), anyString(), anyString()))
        .thenReturn(instruction());
    when(authzClient.evaluate(eq("CREATE"), any(), anyString(), anyString(), any()))
        .thenReturn(new PolicyDecision(true, List.of("basis"), List.of()))
        .thenReturn(new PolicyDecision(false, List.of(), List.of("revoked")));
    SkillRunResult phase1 =
        skill.phase1(new CreateParams("20260720-FICC-I-1", 1_000_000d, "2026-07-21"), creator());

    SkillRunResult result = skill.confirm(phase1.pendingId(), "go", creator());

    assertEquals("skill.create_payment.recheck_denied", result.intentId());
  }
}
