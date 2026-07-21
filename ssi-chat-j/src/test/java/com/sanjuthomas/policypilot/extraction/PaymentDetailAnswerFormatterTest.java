package com.sanjuthomas.policypilot.extraction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.formatting.TimestampFormat;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class PaymentDetailAnswerFormatterTest {

  private PaymentDetailAnswerFormatter formatter;
  private TimestampFormat timestampFormat;

  @BeforeEach
  void setUp() {
    timestampFormat = new TimestampFormat();
    formatter =
        new PaymentDetailAnswerFormatter(
            new AnswerRenderer(
                new AnswerTemplateConfig().answerTemplateEngine(),
                new MoneyFormat(),
                new PolicyBasisFormat()),
            new MoneyFormat(),
            timestampFormat);
  }

  @Test
  void formatsPaymentCardFromApiPayload() {
    Map<String, Object> payload = new HashMap<>();
    payload.put("payment_id", "20260712-FICC-P-2");
    payload.put("instruction_id", "20260712-FICC-I-1");
    payload.put("status", "APPROVED");
    payload.put("amount", 15_000_000);
    payload.put("currency", "USD");
    payload.put("value_date", "2026-07-13");
    payload.put("owning_lob", "FICC");
    payload.put(
        "created_by",
        Map.of("user_id", "pay-101", "given_name", "Emily", "family_name", "Rodriguez"));
    payload.put(
        "approved_by",
        Map.of("user_id", "ficc-500", "given_name", "Caroline", "family_name", "Nguyen"));
    payload.put("approved_at", "2026-07-12T10:00:00Z");

    String answer = formatter.format(payload);
    assertTrue(answer.contains("### Payment `20260712-FICC-P-2`"));
    assertTrue(answer.contains("USD 15,000,000"));
    assertTrue(answer.contains("Rodriguez, Emily (pay-101)"));
    assertTrue(
        answer.contains("Approved at: " + timestampFormat.formatLocal("2026-07-12T10:00:00Z")));
  }

  @Test
  void resolveTargetPrefersRouterThenSequenceId() {
    RouterDecision decision = new RouterDecision();
    decision.setExtractionTarget("payment");
    assertEquals(
        "payment",
        DocumentExtractionService.resolveTarget("Show me 20260720-FICC-I-1", decision));

    RouterDecision empty = new RouterDecision();
    assertEquals(
        "instruction",
        DocumentExtractionService.resolveTarget("Show me 20260720-FICC-I-1", empty));
    assertEquals(
        "payment", DocumentExtractionService.resolveTarget("Show me 20260720-FICC-P-8", empty));
  }
}
