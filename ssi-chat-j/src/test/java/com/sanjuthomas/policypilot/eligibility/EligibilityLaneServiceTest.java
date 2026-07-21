package com.sanjuthomas.policypilot.eligibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class EligibilityLaneServiceTest {

  private EligibilityLaneService service;

  @BeforeEach
  void setUp() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    FakeEligibilityClient client =
        new FakeEligibilityClient().returning(Map.of("payment_id", "20260720-FICC-P-8"));
    service = new EligibilityLaneService(client, new EligibilityAnswerFormatter(renderer));
  }

  @Test
  void paymentApproveFormatsAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    LaneAnswer answer =
        service.answer("Who can approve 20260720-FICC-P-8?", subject(), decision);
    assertEquals("eligibility", answer.recordedPath());
    assertEquals("eligibility_api", answer.synthesis());
    assertTrue(answer.answer().contains("Live OPA") || answer.answer().contains("payment"));
  }

  @Test
  void paymentApproveMissingId() {
    RouterDecision decision = new RouterDecision();
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    LaneAnswer answer = service.answer("Who can approve a payment?", subject(), decision);
    assertTrue(answer.answer().contains("Please include a payment id"));
  }

  @Test
  void unhandledTargetReturnsNull() {
    RouterDecision decision = new RouterDecision();
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("CANCEL");
    assertNull(service.answer("Cancel payment?", subject(), decision));
  }

  private static Subject subject() {
    return new Subject(
        "comp-001",
        "Comp",
        "One",
        "Analyst",
        "FICC",
        List.of("COMPLIANCE_ANALYST"),
        List.of(),
        null,
        List.of(),
        "tok",
        "sess");
  }
}
