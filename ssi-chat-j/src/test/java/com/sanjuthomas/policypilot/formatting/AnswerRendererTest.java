package com.sanjuthomas.policypilot.formatting;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.eligibility.EligiblePaymentApproversView;
import com.sanjuthomas.policypilot.eligibility.EligiblePaymentApproversView.ApproverRow;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AnswerRendererTest {

  private AnswerRenderer renderer;

  @BeforeEach
  void setUp() {
    renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
  }

  @Test
  void renderProcessesTextTemplate() {
    String markdown =
        renderer.render(
            "eligible-payment-approvers",
            new EligiblePaymentApproversView(
                "PAY-1",
                "SUBMITTED",
                10,
                "USD",
                "FICC",
                "INS-1",
                "APPROVED",
                null,
                List.of(
                    new ApproverRow(
                        "Smith", "pay-101", "FO", List.of("role:FUNDING_APPROVER"))),
                List.of(),
                2));

    assertTrue(markdown.contains("PAY-1"));
    assertTrue(markdown.contains("Smith"));
    assertTrue(markdown.contains("USD 10.00"));
  }
}
