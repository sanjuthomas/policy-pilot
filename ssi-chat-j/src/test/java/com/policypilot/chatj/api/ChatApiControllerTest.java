package com.policypilot.chatj.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.policypilot.chatj.TestFixtures;
import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.api.ApiModels.LoginRequest;
import com.policypilot.chatj.auth.FakeSubjectResolver;
import com.policypilot.chatj.auth.FakeZitadelAuthClient;
import com.policypilot.chatj.auth.SessionCredentials;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.config.AppConfig.ZitadelPatProvider;
import com.policypilot.chatj.config.ChatJProperties;
import com.policypilot.chatj.service.FakeChatService;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class ChatApiControllerTest {

  private ChatJProperties properties;
  private FakeZitadelAuthClient zitadelAuthClient;
  private ZitadelPatProvider patProvider;
  private FakeSubjectResolver subjectResolver;
  private FakeChatService chatService;
  private ChatApiController controller;

  @BeforeEach
  void setUp() {
    properties = TestFixtures.properties();
    zitadelAuthClient = new FakeZitadelAuthClient();
    patProvider = new ZitadelPatProvider(properties);
    subjectResolver = new FakeSubjectResolver(zitadelAuthClient);
    chatService = new FakeChatService();
    controller =
        new ChatApiController(
            zitadelAuthClient, patProvider, subjectResolver, chatService, properties);
  }

  @Test
  void healthReturnsUp() {
    assertEquals("UP", controller.health().get("status"));
  }

  @Test
  void loginRequiresPat() {
    ChatApiController noPatController =
        new ChatApiController(
            zitadelAuthClient,
            new ZitadelPatProvider(TestFixtures.propertiesWithoutPat()),
            subjectResolver,
            chatService,
            TestFixtures.propertiesWithoutPat());
    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> noPatController.login(new LoginRequest("alice", "secret")));
    assertEquals(HttpStatus.SERVICE_UNAVAILABLE, ex.getStatusCode());
  }

  @Test
  void loginRequiresCredentials() {
    ResponseStatusException ex =
        assertThrows(ResponseStatusException.class, () -> controller.login(null));
    assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
  }

  @Test
  void loginReturnsSessionFields() {
    zitadelAuthClient.onLogin(
        (login, password) -> new SessionCredentials("sess", "tok", "alice"));

    var response = controller.login(new LoginRequest("alice", "secret"));

    assertEquals("alice", response.user_id());
    assertEquals("sess", response.session_id());
    assertEquals("tok", response.session_token());
  }

  @Test
  void loginMapsFailuresToUnauthorized() {
    zitadelAuthClient.onLoginFailure(new IllegalStateException("nope"));

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> controller.login(new LoginRequest("alice", "bad")));
    assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
  }

  @Test
  void chatRequiresMessage() {
    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class, () -> controller.chat(null, "Bearer tok", "sess"));
    assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
  }

  @Test
  void chatRequiresBearerAuthorization() {
    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> controller.chat(new ChatRequest("hi", List.of(), null), "Basic x", "sess"));
    assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
  }

  @Test
  void chatRequiresAllowedRole() {
    subjectResolver.returning(
        new Subject(
            "u1",
            "A",
            "B",
            "T",
            "LOB",
            List.of("OTHER"),
            List.of(),
            null,
            List.of(),
            "tok",
            "sess"));

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () ->
                controller.chat(
                    new ChatRequest("Who can approve payment PAY-1?", List.of(), null),
                    "Bearer tok",
                    "sess"));
    assertEquals(HttpStatus.FORBIDDEN, ex.getStatusCode());
  }

  @Test
  void chatDelegatesToService() {
    Subject subject =
        new Subject(
            "comp-001",
            "A",
            "B",
            "Analyst",
            "FICC",
            List.of("COMPLIANCE_ANALYST"),
            List.of(),
            null,
            List.of(),
            "tok",
            "sess");
    ChatResponse expected =
        ChatResponse.of(
            "answer",
            new ApiModels.AnswerRoutingInfo("eligibility", "none", "stub", "L", null, null, null));
    subjectResolver.returning(subject);
    chatService.returning(expected);

    ChatResponse response =
        controller.chat(
            new ChatRequest("Who can approve payment PAY-1?", List.of(), null),
            "Bearer tok",
            "sess");

    assertEquals("answer", response.answer());
  }
}
