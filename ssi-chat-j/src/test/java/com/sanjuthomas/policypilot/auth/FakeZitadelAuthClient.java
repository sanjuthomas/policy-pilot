package com.sanjuthomas.policypilot.auth;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.config.AppConfig.ZitadelPatProvider;
import java.util.HashMap;
import java.util.Map;
import java.util.function.BiFunction;
import java.util.function.Function;
import org.springframework.web.client.RestTemplate;

/** Test double for {@link ZitadelAuthClient} — no Mockito required. */
public class FakeZitadelAuthClient extends ZitadelAuthClient {

  private BiFunction<String, String, SessionCredentials> loginHandler =
      (login, password) -> new SessionCredentials("sess", "tok", login.split("@")[0]);
  private BiFunction<String, String, Map<String, Object>> sessionHandler =
      (sessionId, token) -> Map.of();
  private Function<String, Map<String, String>> metadataHandler = userId -> Map.of();
  private RuntimeException metadataError;

  public FakeZitadelAuthClient() {
    super(
        new RestTemplate(),
        TestFixtures.properties(),
        new ZitadelPatProvider(TestFixtures.properties()));
  }

  public FakeZitadelAuthClient onLogin(BiFunction<String, String, SessionCredentials> handler) {
    this.loginHandler = handler;
    return this;
  }

  public FakeZitadelAuthClient onLoginFailure(RuntimeException error) {
    this.loginHandler = (login, password) -> { throw error; };
    return this;
  }

  public FakeZitadelAuthClient onGetSession(BiFunction<String, String, Map<String, Object>> handler) {
    this.sessionHandler = handler;
    return this;
  }

  public FakeZitadelAuthClient onFetchMetadata(Function<String, Map<String, String>> handler) {
    this.metadataHandler = handler;
    return this;
  }

  public FakeZitadelAuthClient onFetchMetadataFailure(RuntimeException error) {
    this.metadataError = error;
    return this;
  }

  @Override
  public SessionCredentials login(String loginName, String password) {
    return loginHandler.apply(loginName, password);
  }

  @Override
  public Map<String, Object> getSession(String sessionId, String sessionToken) {
    return new HashMap<>(sessionHandler.apply(sessionId, sessionToken));
  }

  @Override
  public Map<String, String> fetchUserMetadata(String zitadelUserId) {
    if (metadataError != null) {
      throw metadataError;
    }
    return new HashMap<>(metadataHandler.apply(zitadelUserId));
  }
}
