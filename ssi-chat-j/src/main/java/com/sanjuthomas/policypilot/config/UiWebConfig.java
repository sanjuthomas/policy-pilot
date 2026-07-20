package com.sanjuthomas.policypilot.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Serves the shared PolicyPilot chat UI copied from Python {@code ssi-chat} at build time.
 *
 * <p>Assets live on {@code classpath:/static/} (app.js, styles.css, …). The HTML references
 * {@code /static/...}, so we expose that prefix explicitly. {@code /} forwards to the same
 * {@code index.html} FastAPI serves on 8092.
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
