package com.sanjuthomas.policypilot.auth;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.config.AppConfig.ZitadelPatProvider;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class ZitadelAuthClientTest {

  private RestTemplate restTemplate;
  private MockRestServiceServer server;
  private ChatJProperties properties;
  private ZitadelPatProvider patProvider;
  private ZitadelAuthClient client;

  @BeforeEach
  void setUp() {
    restTemplate = new RestTemplateBuilder().build();
    server = MockRestServiceServer.bindTo(restTemplate).build();
    properties = TestFixtures.properties();
    patProvider = new ZitadelPatProvider(properties);
    client = new ZitadelAuthClient(restTemplate, properties, patProvider);
  }

  @Test
  void loginNameForUserAppendsDomainWhenMissing() {
    assertEquals("alice@ssi.local", client.loginNameForUser("alice"));
    assertEquals("bob@corp.com", client.loginNameForUser("bob@corp.com"));
  }

  @Test
  void loginCreatesSessionFromSnakeCaseFields() {
    server
        .expect(requestTo("http://zitadel-internal:8080/v2/sessions"))
        .andExpect(method(HttpMethod.POST))
        .andExpect(header("Authorization", "Bearer test-pat"))
        .andRespond(withSuccess("{\"session_id\":\"sess-1\",\"session_token\":\"tok-1\"}", MediaType.APPLICATION_JSON));

    SessionCredentials session = client.login("alice@ssi.local", "secret");

    assertEquals("sess-1", session.sessionId());
    assertEquals("tok-1", session.sessionToken());
    assertEquals("alice", session.userId());
    server.verify();
  }

  @Test
  void loginRetriesLocalPartWhenEmailLoginFails() {
    server
        .expect(requestTo("http://zitadel-internal:8080/v2/sessions"))
        .andRespond(org.springframework.test.web.client.response.MockRestResponseCreators.withUnauthorizedRequest());
    server
        .expect(requestTo("http://zitadel-internal:8080/v2/sessions"))
        .andRespond(withSuccess("{\"sessionId\":\"sess-2\",\"sessionToken\":\"tok-2\"}", MediaType.APPLICATION_JSON));

    SessionCredentials session = client.login("alice@ssi.local", "secret");

    assertEquals("sess-2", session.sessionId());
    assertEquals("alice", session.userId());
    server.verify();
  }

  @Test
  void loginRethrowsRuntimeExceptionFromLastAttempt() {
    server
        .expect(requestTo("http://zitadel-internal:8080/v2/sessions"))
        .andRespond(org.springframework.test.web.client.response.MockRestResponseCreators.withBadRequest());

    assertThrows(
        org.springframework.web.client.RestClientResponseException.class,
        () -> client.login("alice", "secret"));
  }

  @Test
  void getSessionReturnsBodyOrEmptyMap() {
    server
        .expect(requestTo(org.hamcrest.Matchers.containsString("/v2/sessions/s1?sessionToken=")))
        .andRespond(withSuccess("{\"session\":{\"id\":\"s1\"}}", MediaType.APPLICATION_JSON));
    server
        .expect(requestTo(org.hamcrest.Matchers.containsString("/v2/sessions/s2?sessionToken=")))
        .andRespond(withSuccess("{}", MediaType.APPLICATION_JSON));

    assertEquals(Map.of("session", Map.of("id", "s1")), client.getSession("s1", "tok"));
    assertTrue(client.getSession("s2", "tok").isEmpty());
    server.verify();
  }

  @Test
  void fetchUserMetadataDecodesBase64Values() {
    String encoded =
        java.util.Base64.getEncoder().encodeToString("Analyst".getBytes(java.nio.charset.StandardCharsets.UTF_8));
    server
        .expect(requestTo("http://zitadel-internal:8080/v2/users/user-1/metadata/search"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(
            withSuccess(
                "{\"metadata\":[{\"key\":\"title\",\"value\":\"" + encoded + "\"}]}",
                MediaType.APPLICATION_JSON));

    Map<String, String> metadata = client.fetchUserMetadata("user-1");

    assertEquals("Analyst", metadata.get("title"));
    server.verify();
  }

  @Test
  void fetchUserMetadataRequiresPat() {
    ZitadelPatProvider emptyPatProvider = new ZitadelPatProvider(TestFixtures.propertiesWithoutPat());
    ZitadelAuthClient noPatClient =
        new ZitadelAuthClient(restTemplate, TestFixtures.propertiesWithoutPat(), emptyPatProvider);
    assertThrows(IllegalStateException.class, () -> noPatClient.fetchUserMetadata("user-1"));
  }

  @Test
  void zitadelBasePrefersInternalUrlAndStripsSlash() {
    assertEquals("http://zitadel-internal:8080", client.zitadelBase());

    ChatJProperties publicOnly =
        new ChatJProperties(
            properties.paymentServiceUrl(),
            properties.instructionServiceUrl(),
            properties.authorizationServiceUrl(),
            properties.indexerUrl(),
            properties.neo4jUri(),
            properties.neo4jUser(),
            properties.neo4jPassword(),
            properties.multimodalVectorIndex(),
            properties.retrievalLimit(),
            "http://zitadel:8080/",
            "",
            properties.zitadelHostHeader(),
            properties.zitadelServicePat(),
            properties.zitadelServicePatFile(),
            properties.oidcIssuerUrl(),
            properties.oidcInternalUrl(),
            properties.oidcAudience(),
            properties.emailDomain(),
            properties.serviceUserId(),
            properties.serviceUserPassword(),
            properties.chatRoles());
    ZitadelAuthClient publicClient =
        new ZitadelAuthClient(restTemplate, publicOnly, patProvider);
    assertEquals("http://zitadel:8080", publicClient.zitadelBase());
  }

  @Test
  void serviceHeadersUsesConfiguredHostHeader() {
    assertEquals("localhost", client.serviceHeaders().getFirst("Host"));
  }

  @Test
  void serviceHeadersDerivesHostFromOidcIssuerWhenHostHeaderBlank() {
    ChatJProperties props =
        new ChatJProperties(
            properties.paymentServiceUrl(),
            properties.instructionServiceUrl(),
            properties.authorizationServiceUrl(),
            properties.indexerUrl(),
            properties.neo4jUri(),
            properties.neo4jUser(),
            properties.neo4jPassword(),
            properties.multimodalVectorIndex(),
            properties.retrievalLimit(),
            properties.zitadelUrl(),
            "",
            "",
            properties.zitadelServicePat(),
            properties.zitadelServicePatFile(),
            "http://issuer.example.com/path",
            properties.oidcInternalUrl(),
            properties.oidcAudience(),
            properties.emailDomain(),
            properties.serviceUserId(),
            properties.serviceUserPassword(),
            properties.chatRoles());
    ZitadelAuthClient issuerClient = new ZitadelAuthClient(restTemplate, props, patProvider);
    assertEquals("issuer.example.com", issuerClient.serviceHeaders().getFirst("Host"));
  }

  @Test
  void decodeMetadataValueFallsBackOnInvalidBase64() {
    assertEquals("plain", ZitadelAuthClient.decodeMetadataValue("plain"));
  }

  @Test
  void isHttpUnauthorizedDetects401() {
    org.springframework.web.client.RestClientResponseException unauthorized =
        new org.springframework.web.client.RestClientResponseException(
            "401", 401, "Unauthorized", null, null, null);
    assertTrue(ZitadelAuthClient.isHttpUnauthorized(unauthorized));
    assertFalse(ZitadelAuthClient.isHttpUnauthorized(new RuntimeException("nope")));
  }
}
