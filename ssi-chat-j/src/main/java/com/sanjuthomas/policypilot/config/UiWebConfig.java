package com.sanjuthomas.policypilot.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Serves the PolicyPilot chat UI from {@code classpath:/static/} ({@code
 * src/main/resources/static}).
 *
 * <p>The HTML references {@code /static/...}, so we expose that prefix explicitly. {@code /}
 * forwards to {@code index.html}.
 */
@Configuration
public class UiWebConfig implements WebMvcConfigurer {

  @Override
  public void addResourceHandlers(ResourceHandlerRegistry registry) {
    registry
        .addResourceHandler("/static/**")
        .addResourceLocations("classpath:/static/")
        .resourceChain(true);
  }

  @Override
  public void addViewControllers(ViewControllerRegistry registry) {
    registry.addViewController("/").setViewName("forward:/static/index.html");
  }
}
