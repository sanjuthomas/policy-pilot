package com.policypilot.chatj.formatting;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import org.junit.jupiter.api.Test;
import org.thymeleaf.spring6.SpringTemplateEngine;

class AnswerTemplateConfigTest {

  @Test
  void answerTemplateEngineBeanBuilds() {
    AnswerTemplateConfig config = new AnswerTemplateConfig();
    SpringTemplateEngine engine = config.answerTemplateEngine();
    assertNotNull(engine);
  }
}
