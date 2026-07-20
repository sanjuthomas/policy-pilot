package com.policypilot.chatj.formatting;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.thymeleaf.context.Context;
import org.thymeleaf.spring6.SpringTemplateEngine;

/** Renders chat answer markdown from Thymeleaf TEXT templates under {@code templates/answers/}. */
@Component
public class AnswerRenderer {

  private final SpringTemplateEngine answerTemplateEngine;

  public AnswerRenderer(
      @Qualifier(AnswerTemplateConfig.ANSWER_TEMPLATE_ENGINE)
          SpringTemplateEngine answerTemplateEngine) {
    this.answerTemplateEngine = answerTemplateEngine;
  }

  public String render(String templateName, Object model) {
    Context context = new Context();
    context.setVariable("m", model);
    return answerTemplateEngine.process(templateName, context).trim();
  }
}
