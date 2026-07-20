package com.policypilot.chatj.formatting;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.thymeleaf.spring6.SpringTemplateEngine;
import org.thymeleaf.templatemode.TemplateMode;
import org.thymeleaf.templateresolver.ClassLoaderTemplateResolver;
import org.thymeleaf.templateresolver.ITemplateResolver;

/** TEXT-mode Thymeleaf engine for chat answer markdown (separate from MVC HTML views). */
@Configuration
public class AnswerTemplateConfig {

  public static final String ANSWER_TEMPLATE_ENGINE = "answerTemplateEngine";

  @Bean(name = ANSWER_TEMPLATE_ENGINE)
  public SpringTemplateEngine answerTemplateEngine() {
    SpringTemplateEngine engine = new SpringTemplateEngine();
    engine.setTemplateResolver(answerTemplateResolver());
    engine.setEnableSpringELCompiler(true);
    return engine;
  }

  private static ITemplateResolver answerTemplateResolver() {
    ClassLoaderTemplateResolver resolver = new ClassLoaderTemplateResolver();
    resolver.setPrefix("templates/answers/");
    resolver.setSuffix(".md");
    resolver.setTemplateMode(TemplateMode.TEXT);
    resolver.setCharacterEncoding("UTF-8");
    resolver.setCheckExistence(true);
    resolver.setCacheable(false);
    return resolver;
  }
}
