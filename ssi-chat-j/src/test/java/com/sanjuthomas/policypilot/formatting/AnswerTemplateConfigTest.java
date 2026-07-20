package com.sanjuthomas.policypilot.formatting;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import org.junit.jupiter.api.Test;
import org.thymeleaf.TemplateEngine;

class AnswerTemplateConfigTest {

  @Test
  void answerTemplateEngineBeanBuilds() {
    AnswerTemplateConfig config = new AnswerTemplateConfig();
    TemplateEngine engine = config.answerTemplateEngine();
    assertNotNull(engine);
  }
}
