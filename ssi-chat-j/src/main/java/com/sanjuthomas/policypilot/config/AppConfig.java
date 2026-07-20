package com.sanjuthomas.policypilot.config;

import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestTemplate;

@Configuration
public class AppConfig {

  @Bean
  RestTemplate restTemplate(RestTemplateBuilder builder) {
    return builder
        .setConnectTimeout(Duration.ofSeconds(10))
        .setReadTimeout(Duration.ofSeconds(60))
        .build();
  }

  @Bean
  ZitadelPatProvider zitadelPatProvider(ChatJProperties properties) {
    return new ZitadelPatProvider(properties);
  }

  public static class ZitadelPatProvider {
    private final ChatJProperties properties;
    private volatile String cached;

    public ZitadelPatProvider(ChatJProperties properties) {
      this.properties = properties;
    }

    public String get() {
      if (StringUtils.hasText(cached)) {
        return cached;
      }
      synchronized (this) {
        if (StringUtils.hasText(cached)) {
          return cached;
        }
        if (StringUtils.hasText(properties.zitadelServicePat())) {
          cached = properties.zitadelServicePat().trim();
          return cached;
        }
        String file = properties.zitadelServicePatFile();
        if (StringUtils.hasText(file)) {
          try {
            cached = Files.readString(Path.of(file)).trim();
            return cached;
          } catch (Exception ex) {
            throw new IllegalStateException("Failed to read ZITADEL PAT file: " + file, ex);
          }
        }
        return "";
      }
    }
  }

  public static boolean hasChatRole(List<String> subjectRoles, List<String> allowed) {
    if (subjectRoles == null || allowed == null) {
      return false;
    }
    for (String role : subjectRoles) {
      if (allowed.contains(role)) {
        return true;
      }
    }
    return false;
  }
}
