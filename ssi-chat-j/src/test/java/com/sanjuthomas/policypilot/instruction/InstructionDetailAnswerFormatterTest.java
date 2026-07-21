package com.sanjuthomas.policypilot.instruction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.formatting.TimestampFormat;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class InstructionDetailAnswerFormatterTest {

  private InstructionDetailAnswerFormatter formatter;
  private TimestampFormat timestampFormat;

  @BeforeEach
  void setUp() {
    timestampFormat = new TimestampFormat();
    formatter =
        new InstructionDetailAnswerFormatter(
            new AnswerRenderer(
                new AnswerTemplateConfig().answerTemplateEngine(),
                new MoneyFormat(),
                new PolicyBasisFormat()),
            timestampFormat);
  }

  @Test
  void formatsInstructionCardFromApiPayload() {
    java.util.Map<String, Object> payload = new java.util.HashMap<>();
    payload.put("instruction_id", "20260717-FICC-I-19");
    payload.put("status", "APPROVED");
    payload.put("instruction_type", "STANDING");
    payload.put("owning_lob", "FICC");
    payload.put("currency", "USD");
    payload.put("wire_scope", "DOMESTIC");
    payload.put("version_number", 2);
    payload.put("effective_date", "2026-07-17T00:00:00");
    payload.put("end_date", "2027-07-17T00:00:00");
    payload.put(
        "created_by",
        Map.of("user_id", "mo-050", "given_name", "David", "family_name", "Okonkwo"));
    payload.put(
        "approved_by",
        Map.of("user_id", "ficc-500", "given_name", "Caroline", "family_name", "Nguyen"));
    payload.put("approved_at", "2026-07-17T10:00:00Z");
    payload.put("creditor", Map.of("name", "Acme"));
    payload.put("creditor_account", Map.of("identification", "999"));

    String answer = formatter.format(payload);

    assertTrue(answer.contains("### Instruction `20260717-FICC-I-19`"));
    assertTrue(answer.contains("**APPROVED**"));
    assertTrue(answer.contains("STANDING"));
    assertTrue(answer.contains("Okonkwo, David (mo-050)"));
    assertTrue(answer.contains("Nguyen, Caroline (ficc-500)"));
    assertTrue(answer.contains("Acme (`999`)"));
    assertTrue(answer.contains("Approved at: " + timestampFormat.formatLocal("2026-07-17T10:00:00Z")));
    assertTrue(!answer.contains("Approved at: 2026-07-17T10:00:00"));
    assertTrue(answer.contains("| Field") && answer.contains("| Value"));
  }

  @Test
  void approverMissingUsesNotYetApproved() {
    InstructionDetailAnswerView view =
        formatter.toView(
            Map.of(
                "instruction_id",
                "INS-1",
                "status",
                "SUBMITTED",
                "created_by",
                Map.of("user_id", "mo-1")));
    assertEquals("— (not yet approved)", view.approver());
    assertEquals("mo-1", view.creator());
  }
}
