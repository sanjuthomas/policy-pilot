package com.policypilot.chatj.auth;

import com.policypilot.chatj.config.ChatJProperties;
import jakarta.annotation.PostConstruct;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
public class ServiceIdentity {

  private static final Logger log = LoggerFactory.getLogger(ServiceIdentity.class);

  private final ZitadelAuthClient zitadelAuthClient;
  private final ChatJProperties properties;
  private final AtomicReference<SessionCredentials> credentials = new AtomicReference<>();

  public ServiceIdentity(ZitadelAuthClient zitadelAuthClient, ChatJProperties properties) {
    this.zitadelAuthClient = zitadelAuthClient;
    this.properties = properties;
  }

  @PostConstruct
  public void loginOnStartup() {
    try {
      ensureLoggedIn();
    } catch (Exception ex) {
      log.warn("ssi-chat-j service identity login deferred: {}", ex.toString());
    }
  }

  public synchronized void ensureLoggedIn() {
    if (credentials.get() != null && StringUtils.hasText(credentials.get().sessionToken())) {
      return;
    }
    Exception last = null;
    for (int attempt = 1; attempt <= 5; attempt++) {
      try {
        SessionCredentials session =
            zitadelAuthClient.login(properties.serviceUserId(), properties.serviceUserPassword());
        credentials.set(session);
        log.info(
            "ssi-chat-j authenticated as {} (session_id={})",
            properties.serviceUserId(),
            session.sessionId());
        return;
      } catch (Exception ex) {
        last = ex;
        log.warn(
            "ssi-chat-j login attempt {}/{} for {} failed: {}",
            attempt,
            5,
            properties.serviceUserId(),
            ex.toString());
        try {
          Thread.sleep(2000L);
        } catch (InterruptedException ie) {
          Thread.currentThread().interrupt();
          throw new IllegalStateException("interrupted during service login", ie);
        }
      }
    }
    throw new IllegalStateException("service identity login failed", last);
  }

  public String token() {
    SessionCredentials session = credentials.get();
    return session == null ? null : session.sessionToken();
  }

  public String sessionId() {
    SessionCredentials session = credentials.get();
    return session == null ? null : session.sessionId();
  }

  public Map<String, String> oboHeaders(String userBearerToken, String userSessionId) {
    ensureLoggedIn();
    String svcToken = token();
    if (!StringUtils.hasText(svcToken)) {
      throw new IllegalStateException(
          "chat service identity not logged in — cannot call domain services with OBO");
    }
    Map<String, String> headers = new HashMap<>();
    headers.put("Authorization", "Bearer " + svcToken);
    headers.put("Accept", "application/json");
    headers.put("X-On-Behalf-Of", userBearerToken);
    if (StringUtils.hasText(sessionId())) {
      headers.put("X-Session-Id", sessionId());
    }
    if (StringUtils.hasText(userSessionId)) {
      headers.put("X-On-Behalf-Of-Session-Id", userSessionId);
    }
    return headers;
  }
}
