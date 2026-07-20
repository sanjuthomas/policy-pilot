package com.policypilot.chatj.eligibility;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.AnswerTemplateConfig;
import com.policypilot.chatj.formatting.MoneyFormat;
import com.policypilot.chatj.formatting.PolicyBasisFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class EligibilityAnswerFormatterTest {

  private EligibilityAnswerFormatter formatter;

  @BeforeEach
  void setUp() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    formatter = new EligibilityAnswerFormatter(renderer);
  }

  @Test
  void formatsLiveOpaHeaderAndApprovers() {
    String answer =
        formatter.formatEligibleApproversAnswer(
            Map.of(
                "payment_id",
                "PAY-1",
                "payment_status",
                "SUBMITTED",
                "amount",
                100,
                "currency",
                "USD",
                "owning_lob",
                "FICC",
                "instruction_id",
                "INS-1",
                "instruction_status",
                "APPROVED",
                "eligible",
                List.of(
                    Map.of(
                        "user_id",
                        "pay-101",
                        "display_name",
                        "Smith, Pat",
                        "title",
                        "FO",
                        "allow_basis",
                        List.of("role:FUNDING_APPROVER"))),
                "candidates_evaluated",
                3));
    assertTrue(answer.contains("Live OPA"));
    assertTrue(answer.contains("Users who can approve"));
    assertTrue(answer.contains("PAY-1"));
    assertTrue(answer.contains("Smith, Pat"));
    assertTrue(answer.contains("Evaluated 3 FUNDING_APPROVER"));
    assertTrue(answer.contains("USD 100.00"));
  }

  @Test
  void formatsBlockedReasonWithProspectiveApprovers() {
    Map<String, Object> data = new LinkedHashMap<>();
    data.put("payment_id", "20260720-FICC-P-8");
    data.put("payment_status", "DRAFT");
    data.put("amount", 12_000_000);
    data.put("currency", "USD");
    data.put("owning_lob", "FICC");
    data.put("instruction_id", "20260720-FICC-I-3");
    data.put("instruction_status", "APPROVED");
    data.put(
        "approval_blocked_reason",
        "Payment approval is not permitted while status is DRAFT. Submit the payment first.");
    data.put("eligible", List.of());
    data.put(
        "prospective_eligible",
        List.of(
            Map.of(
                "user_id",
                "pay-300",
                "display_name",
                "Bergmann, Thomas",
                "title",
                "Managing Director",
                "allow_basis",
                List.of(
                    "amount 1.2e+07 within subject and absolute limits",
                    "covers LOB FICC"))));
    data.put("candidates_evaluated", 6);

    String answer = formatter.formatEligibleApproversAnswer(data);
    assertTrue(answer.contains("Live OPA"));
    assertTrue(answer.contains("not permitted while status is DRAFT"));
    assertTrue(answer.contains("After the payment is submitted (DRAFT → SUBMITTED)"));
    assertTrue(answer.contains("Bergmann, Thomas"));
    assertTrue(answer.contains("amount $12 million within subject and absolute limits"));
    assertTrue(answer.contains("Evaluated 6 FUNDING_APPROVER"));
    assertTrue(answer.contains("USD 12,000,000.00"));
  }

  @Test
  void formatsEligibleSubmittersAnswer() {
    String answer =
        formatter.formatEligibleSubmittersAnswer(
            Map.of(
                "payment_id",
                "PAY-DRAFT",
                "payment_status",
                "DRAFT",
                "amount",
                1000,
                "currency",
                "USD",
                "owning_lob",
                "FICC",
                "instruction_id",
                "INS-1",
                "instruction_status",
                "APPROVED",
                "eligible",
                List.of(
                    Map.of(
                        "user_id",
                        "mo-100",
                        "display_name",
                        "Chen, Sarah",
                        "title",
                        "Analyst",
                        "allow_basis",
                        List.of("role PAYMENT_CREATOR"))),
                "candidates_evaluated",
                4));
    assertTrue(answer.contains("Live OPA evaluation for submitting payment"));
    assertTrue(answer.contains("Users who can submit this payment for funding approval"));
    assertTrue(answer.contains("Chen, Sarah"));
    assertTrue(answer.contains("Evaluated 4 PAYMENT_CREATOR"));
  }

  @Test
  void formatsSubmitBlockedReason() {
    String answer =
        formatter.formatEligibleSubmittersAnswer(
            Map.of(
                "payment_id",
                "PAY-SUB",
                "payment_status",
                "SUBMITTED",
                "amount",
                10,
                "currency",
                "USD",
                "owning_lob",
                "FICC",
                "instruction_status",
                "APPROVED",
                "submit_blocked_reason",
                "Only DRAFT payments can be submitted.",
                "eligible",
                List.of()));
    assertTrue(answer.contains("Live OPA evaluation for submitting payment"));
    assertTrue(answer.contains("Only DRAFT payments can be submitted."));
  }
}
