package com.policypilot.chatj.eligibility;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class EligibilityFormatterTest {

  @Test
  void formatsLiveOpaHeaderAndApprovers() {
    String answer =
        EligibilityFormatter.formatEligibleApproversAnswer(
            Map.of(
                "payment_id", "PAY-1",
                "payment_status", "SUBMITTED",
                "amount", 100,
                "currency", "USD",
                "owning_lob", "FICC",
                "instruction_id", "INS-1",
                "instruction_status", "APPROVED",
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
  }
}
