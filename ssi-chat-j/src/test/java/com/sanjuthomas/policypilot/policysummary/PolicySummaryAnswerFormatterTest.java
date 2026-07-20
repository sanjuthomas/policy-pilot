package com.sanjuthomas.policypilot.policysummary;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PolicySummaryAnswerFormatterTest {

  @Test
  void formatsInstructionApprovalSummary() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    PolicySummaryAnswerFormatter formatter =
        new PolicySummaryAnswerFormatter(renderer, new IdentityTokenFormat());

    String answer =
        formatter.format(
            Map.of(
                "domain",
                "instruction",
                "action",
                "APPROVE",
                "title",
                "Instruction approval",
                "narrative",
                "Someone with the INSTRUCTION_APPROVER role may approve — subject to four-eyes.",
                "requires",
                List.of(Map.of("kind", "role", "value", "INSTRUCTION_APPROVER")),
                "source",
                "opa"));

    assertTrue(answer.contains("**Instruction approval**"));
    assertTrue(answer.contains("`instruction` / `APPROVE`"));
    assertTrue(answer.contains("`INSTRUCTION_APPROVER`"));
    assertTrue(answer.contains("authorization-service"));
    assertTrue(answer.contains("four-eyes"));
  }
}
