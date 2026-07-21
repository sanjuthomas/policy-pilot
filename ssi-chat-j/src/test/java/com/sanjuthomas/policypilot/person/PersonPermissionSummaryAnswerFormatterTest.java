package com.sanjuthomas.policypilot.person;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PersonPermissionSummaryAnswerFormatterTest {

  private final PersonPermissionSummaryAnswerFormatter formatter =
      new PersonPermissionSummaryAnswerFormatter(
          new AnswerRenderer(
              new AnswerTemplateConfig().answerTemplateEngine(),
              new MoneyFormat(),
              new PolicyBasisFormat()),
          new IdentityTokenFormat());

  @Test
  void formatsSingleMatch() {
    String text =
        formatter.format(
            Map.of(
                "query",
                "Kowalski, Anna",
                "count",
                1,
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
                        List.of("PAYMENT_CREATOR", "FUNDING_APPROVER"),
                        "groups",
                        List.of("MIDDLE_OFFICE"),
                        "amount_clubs",
                        List.of("UP_TO_100_MILLION_CLUB"),
                        "covering_lobs",
                        List.of("FX"),
                        "capabilities",
                        List.of(
                            Map.of(
                                "kind",
                                "funding_approve",
                                "description",
                                "Approve/reject payments for covering LOBs (FX)")),
                        "narrative",
                        "Kowalski, Anna (pay-203) is a dual-role funding approver."))));

    assertTrue(text.contains("Kowalski, Anna"));
    assertTrue(text.contains("pay-203"));
    assertTrue(text.contains("funding_approve"));
    assertTrue(text.contains("`UP_TO_100_MILLION_CLUB`"));
    assertTrue(text.contains("`FUNDING_APPROVER`"));
    assertTrue(text.contains("`MIDDLE_OFFICE`"));
    assertTrue(text.contains("ZITADEL"));
  }

  @Test
  void formatsEmptyMatches() {
    String text =
        formatter.format(Map.of("query", "nobody-here", "count", 0, "matches", List.of()));
    assertTrue(text.contains("No users matched `nobody-here`"));
    assertTrue(text.contains("pay-203"));
  }

  @Test
  void formatsAmbiguousMatches() {
    String text =
        formatter.format(
            Map.of(
                "query",
                "Anna",
                "count",
                2,
                "matches",
                List.of(
                    Map.of(
                        "user_id", "pay-203", "display_name", "Kowalski, Anna", "title", "Associate"),
                    Map.of(
                        "user_id", "other", "display_name", "Other, Anna", "title", "Analyst"))));
    assertTrue(text.contains("Multiple users matched `Anna`"));
    assertTrue(text.contains("pay-203"));
    assertTrue(text.contains("other"));
  }
}
