package com.sanjuthomas.policypilot.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.api.ApiModels.LoginRequest;
import com.sanjuthomas.policypilot.auth.ChatUsersDirectory;
import com.sanjuthomas.policypilot.auth.FakeSubjectResolver;
import com.sanjuthomas.policypilot.auth.FakeZitadelAuthClient;
import com.sanjuthomas.policypilot.auth.SessionCredentials;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.api.ApiModels.ChatFeedbackRequest;
import com.sanjuthomas.policypilot.api.ApiModels.SkillConfirmRequest;
import com.sanjuthomas.policypilot.config.AppConfig.ZitadelPatProvider;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import com.sanjuthomas.policypilot.eligibility.FakeEligibilityClient;
import com.sanjuthomas.policypilot.observability.ChatAnswerFinalizer;
import com.sanjuthomas.policypilot.observability.FeedbackDistributionTracker;
import com.sanjuthomas.policypilot.observability.FeedbackMetrics;
import com.sanjuthomas.policypilot.observability.RoutingDistributionTracker;
import com.sanjuthomas.policypilot.observability.RoutingMetrics;
import com.sanjuthomas.policypilot.observability.SkillMetrics;
import com.sanjuthomas.policypilot.service.FakeChatService;
import com.sanjuthomas.policypilot.skill.ApprovePaymentSkill;
import com.sanjuthomas.policypilot.skill.CancelPaymentSkill;
import com.sanjuthomas.policypilot.skill.CreatePaymentSkill;
import com.sanjuthomas.policypilot.skill.PaymentSkillService;
import com.sanjuthomas.policypilot.skill.PendingSkillStore;
import com.sanjuthomas.policypilot.skill.SubmitPaymentSkill;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.List;
import java.util.Map;
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
  private ChatUsersDirectory chatUsersDirectory;
  private FeedbackDistributionTracker feedbackDistributionTracker;
  private RoutingDistributionTracker routingDistributionTracker;
  private ChatApiController controller;

  private static PaymentSkillService paymentSkillService() {
    PendingSkillStore store = new PendingSkillStore();
    FakeEligibilityClient eligibilityClient = new FakeEligibilityClient();
    return new PaymentSkillService(
        new CreatePaymentSkill(eligibilityClient, null, null, store),
        new SubmitPaymentSkill(eligibilityClient, null, null, store),
        new ApprovePaymentSkill(eligibilityClient, null, null, store),
        new CancelPaymentSkill(eligibilityClient, null, null, store));
  }

  private static ChatAnswerFinalizer answerFinalizer() {
    SimpleMeterRegistry registry = new SimpleMeterRegistry();
    return new ChatAnswerFinalizer(
        new RoutingMetrics(registry, new RoutingDistributionTracker()), new SkillMetrics(registry));
  }

  @BeforeEach
  void setUp() {
    properties = TestFixtures.properties();
    zitadelAuthClient = new FakeZitadelAuthClient();
    patProvider = new ZitadelPatProvider(properties);
    subjectResolver = new FakeSubjectResolver(zitadelAuthClient);
    chatService = new FakeChatService();
    chatUsersDirectory = new ChatUsersDirectory(properties);
    feedbackDistributionTracker = new FeedbackDistributionTracker();
    routingDistributionTracker = new RoutingDistributionTracker();
    FeedbackMetrics feedbackMetrics =
        new FeedbackMetrics(new SimpleMeterRegistry(), feedbackDistributionTracker);
    controller =
        new ChatApiController(
            zitadelAuthClient,
            patProvider,
            subjectResolver,
            chatService,
            properties,
            chatUsersDirectory,
            feedbackMetrics,
            routingDistributionTracker,
            feedbackDistributionTracker,
            paymentSkillService(),
            answerFinalizer());
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
            TestFixtures.propertiesWithoutPat(),
            chatUsersDirectory,
            new FeedbackMetrics(new SimpleMeterRegistry(), feedbackDistributionTracker),
            routingDistributionTracker,
            feedbackDistributionTracker,
            paymentSkillService(),
            answerFinalizer());
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
    assertEquals(List.of(), response.roles());
    assertEquals(List.of(), response.audiences());
  }

  @Test
  void loginResolvesRolesAndAudiencesFromSeed() {
    zitadelAuthClient.onLogin(
        (login, password) -> new SessionCredentials("sess", "tok", "pay-205"));

    var response = controller.login(new LoginRequest("pay-205", "secret"));

    assertEquals("pay-205", response.user_id());
    assertTrue(response.roles().contains("PAYMENT_CREATOR"));
    assertTrue(response.roles().contains("FUNDING_APPROVER"));
    assertTrue(response.audiences().contains("payment_creator"));
    assertTrue(response.audiences().contains("funding_approver"));
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

  @Test
  void confirmCreatePaymentRequiresPendingId() {
    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () ->
                controller.confirmCreatePayment(
                    new SkillConfirmRequest("", "go"), "Bearer tok", "sess"));
    assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
  }

  @Test
  void confirmCreatePaymentUnknownPendingReturnsExpiredAnswer() {
    subjectResolver.returning(
        new Subject(
            "pay-101",
            "Emily",
            "Rodriguez",
            "Analyst",
            "FICC",
            List.of("PAYMENT_CREATOR"),
            List.of("MIDDLE_OFFICE"),
            "pay-300",
            List.of(),
            "tok",
            "sess"));

    ChatResponse response =
        controller.confirmCreatePayment(
            new SkillConfirmRequest("does-not-exist", "no_go"), "Bearer tok", "sess");

    assertEquals("skill", response.routing().path());
    assertEquals("skill.create_payment.pending_missing", response.routing().intent_id());
    assertTrue(response.answer().toLowerCase().contains("expired"));
  }

  @Test
  void chatUsersReturnsSeedRoster() {
    var body = controller.chatUsers();
    assertTrue(((java.util.List<?>) body.get("users")).size() > 0);
  }

  @Test
  void routingStatsStartsEmpty() {
    Map<String, Object> stats = controller.routingStats();
    assertEquals(0L, stats.get("total"));
  }

  @Test
  void feedbackRecordsUpVote() {
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
    subjectResolver.returning(subject);

    Map<String, String> body =
        controller.chatFeedback(
            new ChatFeedbackRequest(
                "up",
                "events",
                "eligibility",
                "none",
                "eligibility_api",
                "eligibility",
                null,
                "abc"),
            "Bearer tok",
            "sess");

    assertEquals("recorded", body.get("status"));
    Map<String, Object> stats = controller.feedbackStats();
    assertEquals(1L, stats.get("up"));
    assertEquals(0L, stats.get("down"));
  }

  @Test
  void feedbackRejectsInvalidRating() {
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
    subjectResolver.returning(subject);

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () ->
                controller.chatFeedback(
                    new ChatFeedbackRequest(
                        "meh", "events", "eligibility", "none", "eligibility_api", null, null, null),
                    "Bearer tok",
                    "sess"));
    assertEquals(HttpStatus.BAD_REQUEST, ex.getStatusCode());
  }
}
