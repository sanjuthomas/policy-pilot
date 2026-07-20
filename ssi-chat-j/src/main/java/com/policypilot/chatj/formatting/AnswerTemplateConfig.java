package com.policypilot.chatj.formatting;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.thymeleaf.TemplateEngine;
import org.thymeleaf.spring6.dialect.SpringStandardDialect;
import org.thymeleaf.templatemode.TemplateMode;
import org.thymeleaf.templateresolver.ClassLoaderTemplateResolver;
import org.thymeleaf.templateresolver.ITemplateResolver;

/**
 * TEXT-mode Thymeleaf for chat answer markdown.
 *
 * <p>Uses plain {@link TemplateEngine} (not {@code SpringTemplateEngine}) so Boot's HTML
 * view engine for {@code templates/*.html} is not displaced. Spring EL dialect avoids a
 * separate OGNL dependency.
 */
@Configuration
public class AnswerTemplateConfig {

  public static final String ANSWER_TEMPLATE_ENGINE = "answerTemplateEngine";

  @Bean(name = ANSWER_TEMPLATE_ENGINE)
  public TemplateEngine answerTemplateEngine() {
    TemplateEngine engine = new TemplateEngine();
    engine.setDialect(new SpringStandardDialect());
    engine.setTemplateResolver(answerTemplateResolver());
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
