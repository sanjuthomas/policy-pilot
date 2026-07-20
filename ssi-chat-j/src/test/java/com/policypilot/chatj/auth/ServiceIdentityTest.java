package com.policypilot.chatj.auth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.TestFixtures;
import com.policypilot.chatj.config.ChatJProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ServiceIdentityTest {

  private ChatJProperties properties;
  private FakeZitadelAuthClient zitadelAuthClient;
  private ServiceIdentity serviceIdentity;

  @BeforeEach
  void setUp() {
    properties = TestFixtures.properties();
    zitadelAuthClient = new FakeZitadelAuthClient();
    serviceIdentity = new ServiceIdentity(zitadelAuthClient, properties);
  }

  @Test
  void loginOnStartupSwallowsFailures() {
    zitadelAuthClient.onLoginFailure(new IllegalStateException("offline"));
    serviceIdentity.loginOnStartup(1, 0L);
    assertNull(serviceIdentity.token());
  }

  @Test
  void ensureLoggedInCachesCredentials() {
    SessionCredentials session = new SessionCredentials("svc-sess", "svc-tok", "svc-chat");
    zitadelAuthClient.onLogin((login, password) -> session);

    serviceIdentity.ensureLoggedIn(1, 0L);
    serviceIdentity.ensureLoggedIn(1, 0L);

    assertEquals("svc-tok", serviceIdentity.token());
    assertEquals("svc-sess", serviceIdentity.sessionId());
  }

  @Test
  void ensureLoggedInRetriesUntilSuccess() {
    SessionCredentials session = new SessionCredentials("svc-sess", "svc-tok", "svc-chat");
    java.util.concurrent.atomic.AtomicInteger attempts = new java.util.concurrent.atomic.AtomicInteger();
    zitadelAuthClient.onLogin(
        (login, password) -> {
          if (attempts.getAndIncrement() == 0) {
            throw new RuntimeException("transient");
          }
          return session;
        });

    serviceIdentity.ensureLoggedIn(3, 0L);

    assertEquals(2, attempts.get());
    assertEquals("svc-tok", serviceIdentity.token());
  }

  @Test
  void ensureLoggedInFailsAfterAttempts() {
    zitadelAuthClient.onLoginFailure(new RuntimeException("still down"));

    IllegalStateException ex =
        assertThrows(IllegalStateException.class, () -> serviceIdentity.ensureLoggedIn(3, 0L));
    assertTrue(ex.getMessage().contains("service identity login failed"));
  }

  @Test
  void ensureLoggedInHonorsInterruptDuringBackoff() {
    zitadelAuthClient.onLoginFailure(new RuntimeException("fail"));
    Thread.currentThread().interrupt();
    try {
      IllegalStateException ex =
          assertThrows(IllegalStateException.class, () -> serviceIdentity.ensureLoggedIn(2, 50L));
      assertTrue(ex.getMessage().contains("interrupted"));
    } finally {
      Thread.interrupted();
    }
  }

  @Test
  void oboHeadersIncludeOnBehalfOfFields() {
    zitadelAuthClient.onLogin(
        (login, password) -> new SessionCredentials("svc-sess", "svc-tok", "svc-chat"));

    var headers = serviceIdentity.oboHeaders("user-tok", "user-sess");

    assertEquals("Bearer svc-tok", headers.get("Authorization"));
    assertEquals("user-tok", headers.get("X-On-Behalf-Of"));
    assertEquals("svc-sess", headers.get("X-Session-Id"));
    assertEquals("user-sess", headers.get("X-On-Behalf-Of-Session-Id"));
  }

  @Test
  void oboHeadersRequireServiceLogin() {
    zitadelAuthClient.onLogin(
        (login, password) -> new SessionCredentials("svc-sess", "", "svc-chat"));

    IllegalStateException ex =
        assertThrows(
            IllegalStateException.class, () -> serviceIdentity.oboHeaders("user-tok", "user-sess"));
    assertTrue(ex.getMessage().contains("not logged in"));
  }
}
