package com.policypilot.chatj.formatting;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.eligibility.EligibleApproversView;
import com.policypilot.chatj.eligibility.EligibleApproversView.ApproverRow;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AnswerRendererTest {

  private AnswerRenderer renderer;

  @BeforeEach
  void setUp() {
    renderer = new AnswerRenderer(new AnswerTemplateConfig().answerTemplateEngine());
  }

  @Test
  void renderProcessesTextTemplate() {
    String markdown =
        renderer.render(
            "eligible-approvers",
            new EligibleApproversView(
                "PAY-1",
                "SUBMITTED",
                "$10.00",
                "FICC",
                "backing instruction INS-1 (APPROVED)",
                null,
                List.of(new ApproverRow(1, "Smith", "FO", "role:FUNDING_APPROVER")),
                2));

    assertTrue(markdown.contains("PAY-1"));
    assertTrue(markdown.contains("Smith"));
  }
}
