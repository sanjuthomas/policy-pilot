package com.policypilot.chatj.eligibility;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.AnswerTemplateConfig;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class EligibilityAnswerFormatterTest {

  private EligibilityAnswerFormatter formatter;

  @BeforeEach
  void setUp() {
    AnswerRenderer renderer = new AnswerRenderer(new AnswerTemplateConfig().answerTemplateEngine());
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
  }

  @Test
  void formatsBlockedReason() {
    String answer =
        formatter.formatEligibleApproversAnswer(
            Map.of(
                "payment_id",
                "PAY-2",
                "payment_status",
                "DRAFT",
                "amount",
                10,
                "currency",
                "USD",
                "owning_lob",
                "FICC",
                "instruction_id",
                "INS-1",
                "instruction_status",
                "APPROVED",
                "approval_blocked_reason",
                "Approval is not permitted while DRAFT.",
                "eligible",
                List.of()));
    assertTrue(answer.contains("Live OPA"));
    assertTrue(answer.contains("not permitted while DRAFT"));
  }
}
