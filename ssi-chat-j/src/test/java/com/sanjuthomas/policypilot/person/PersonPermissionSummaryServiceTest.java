package com.sanjuthomas.policypilot.person;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.FakeEligibilityClient;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PersonPermissionSummaryServiceTest {

  private final PersonPermissionSummaryAnswerFormatter formatter =
      new PersonPermissionSummaryAnswerFormatter(
          new AnswerRenderer(
              new AnswerTemplateConfig().answerTemplateEngine(),
              new MoneyFormat(),
              new PolicyBasisFormat()),
          new IdentityTokenFormat());

  @Test
  void usesPersonQuerySlot() {
    FakeEligibilityClient client =
        new FakeEligibilityClient()
            .returning(
                Map.of(
                    "query",
                    "pay-203",
                    "matches",
                    List.of(
                        Map.of(
                            "user_id",
                            "pay-203",
                            "display_name",
                            "Kowalski, Anna",
                            "title",
                            "Associate",
                            "roles",
                            List.of("PAYMENT_CREATOR"),
                            "groups",
                            List.of("MIDDLE_OFFICE"),
                            "amount_clubs",
                            List.of(),
                            "covering_lobs",
                            List.of("FX"),
                            "capabilities",
                            List.of(),
                            "narrative",
                            ""))));
    RouterDecision decision = new RouterDecision();
    decision.setPath("person_permissions");
    decision.setPersonQuery("pay-203");

    LaneAnswer lane =
        new PersonPermissionSummaryService(client, formatter)
            .answer("ignored text", subject(), decision);

    assertEquals("person_permissions", lane.recordedPath());
    assertEquals("eligibility_api", lane.synthesis());
    assertTrue(lane.answer().contains("pay-203"));
  }

  @Test
  void fallsBackToSlotParseWhenPersonQueryMissing() {
    FakeEligibilityClient client =
        new FakeEligibilityClient()
            .returning(
                Map.of(
                    "query",
                    "Kowalski, Anna",
                    "matches",
                    List.of(
                        Map.of(
                            "user_id",
                            "pay-203",
                            "display_name",
                            "Kowalski, Anna",
                            "title",
                            "Associate",
                            "roles",
                            List.of(),
                            "groups",
                            List.of(),
                            "amount_clubs",
                            List.of(),
                            "covering_lobs",
                            List.of(),
                            "capabilities",
                            List.of(),
                            "narrative",
                            ""))));
    RouterDecision decision = new RouterDecision();
    decision.setPath("person_permissions");

    LaneAnswer lane =
        new PersonPermissionSummaryService(client, formatter)
            .answer("permissions of Kowalski, Anna", subject(), decision);

    assertTrue(lane.answer().contains("Kowalski, Anna"));
  }

  @Test
  void asksForClarificationWhenQueryUnresolved() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("person_permissions");
    LaneAnswer lane =
        new PersonPermissionSummaryService(new FakeEligibilityClient(), formatter)
            .answer("tell me something vague", subject(), decision);
    assertTrue(lane.answer().contains("Ask again"));
    assertEquals("person_permissions", lane.recordedPath());
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
