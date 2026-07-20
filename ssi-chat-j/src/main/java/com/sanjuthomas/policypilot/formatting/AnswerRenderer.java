package com.sanjuthomas.policypilot.formatting;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.thymeleaf.TemplateEngine;
import org.thymeleaf.context.Context;

/** Renders chat answer markdown from Thymeleaf TEXT templates under {@code templates/answers/}. */
@Component
public class AnswerRenderer {

  private final TemplateEngine answerTemplateEngine;
  private final MoneyFormat moneyFormat;
  private final PolicyBasisFormat policyBasisFormat;

  public AnswerRenderer(
      @Qualifier(AnswerTemplateConfig.ANSWER_TEMPLATE_ENGINE) TemplateEngine answerTemplateEngine,
      MoneyFormat moneyFormat,
      PolicyBasisFormat policyBasisFormat) {
    this.answerTemplateEngine = answerTemplateEngine;
    this.moneyFormat = moneyFormat;
    this.policyBasisFormat = policyBasisFormat;
  }

  public String render(String templateName, Object model) {
    Context context = new Context();
    context.setVariable("m", model);
    // Presentation helpers for templates (not view-model state).
    context.setVariable("money", moneyFormat);
    context.setVariable("basis", policyBasisFormat);
    return answerTemplateEngine.process(templateName, context).trim();
  }
}
