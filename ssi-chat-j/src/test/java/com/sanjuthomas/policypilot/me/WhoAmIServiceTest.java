package com.sanjuthomas.policypilot.me;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import java.util.List;
import org.junit.jupiter.api.Test;

class WhoAmIServiceTest {

  private static WhoAmIService service() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    return new WhoAmIService(renderer, new IdentityTokenFormat());
  }

  @Test
  void formatsPay205IdentityTokens() {
    Subject subject =
        new Subject(
            "pay-205",
            "Fatima",
            "Al-Rashid",
            "Vice President",
            null,
            List.of("PAYMENT_CREATOR", "FUNDING_APPROVER"),
            List.of("MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"),
            "pay-300",
            List.of("FICC"),
            "tok",
            "sess");

    String answer = service().answer(subject);

    assertTrue(answer.contains("Al-Rashid, Fatima"));
    assertTrue(answer.contains("`pay-205`") || answer.contains("(`pay-205`)"));
    assertTrue(answer.contains("**Roles:**"));
    assertTrue(answer.contains("`PAYMENT_CREATOR`"));
    assertTrue(answer.contains("`FUNDING_APPROVER`"));
    assertTrue(answer.contains("**Amount clubs:**"));
    assertTrue(answer.contains("`UP_TO_1_BILLION_CLUB`"));
    assertTrue(answer.contains("`MIDDLE_OFFICE`"));
    assertTrue(answer.contains("funding approver"));
    assertTrue(answer.contains("payment creator"));
    assertFalse(answer.contains("PAYMENTCREATOR"));
    assertFalse(answer.contains("UPTO1BILLIONCLUB"));
  }
}
