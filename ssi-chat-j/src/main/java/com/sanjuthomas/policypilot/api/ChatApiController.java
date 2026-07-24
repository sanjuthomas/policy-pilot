package com.sanjuthomas.policypilot.api;

import com.sanjuthomas.policypilot.api.ApiModels.ChatFeedbackRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.api.ApiModels.LoginRequest;
import com.sanjuthomas.policypilot.api.ApiModels.LoginResponse;
import com.sanjuthomas.policypilot.api.ApiModels.SkillConfirmRequest;
import com.sanjuthomas.policypilot.auth.AudienceLabels;
import com.sanjuthomas.policypilot.auth.ChatUsersDirectory;
import com.sanjuthomas.policypilot.auth.DirectoryUser;
import com.sanjuthomas.policypilot.auth.SessionCredentials;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.auth.SubjectResolver;
import com.sanjuthomas.policypilot.auth.ZitadelAuthClient;
import com.sanjuthomas.policypilot.config.AppConfig;
import com.sanjuthomas.policypilot.config.AppConfig.ZitadelPatProvider;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import com.sanjuthomas.policypilot.observability.ChatFeedbackContext;
import com.sanjuthomas.policypilot.observability.FeedbackDistributionTracker;
import com.sanjuthomas.policypilot.observability.FeedbackMetrics;
import com.sanjuthomas.policypilot.observability.ChatAnswerFinalizer;
import com.sanjuthomas.policypilot.observability.RoutingDistributionTracker;
import com.sanjuthomas.policypilot.service.ChatService;
import com.sanjuthomas.policypilot.skill.PaymentSkillService;
import com.sanjuthomas.policypilot.skill.SkillRunResult;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class ChatApiController {

  private static final Logger log = LoggerFactory.getLogger(ChatApiController.class);
  private static final Set<String> FEEDBACK_RATINGS = Set.of("up", "down");

  private final ZitadelAuthClient zitadelAuthClient;
  private final ZitadelPatProvider patProvider;
  private final SubjectResolver subjectResolver;
  private final ChatService chatService;
  private final ChatJProperties properties;
  private final ChatUsersDirectory chatUsersDirectory;
  private final FeedbackMetrics feedbackMetrics;
  private final RoutingDistributionTracker routingDistributionTracker;
  private final FeedbackDistributionTracker feedbackDistributionTracker;
  private final PaymentSkillService paymentSkillService;
  private final ChatAnswerFinalizer answerFinalizer;

  public ChatApiController(
      ZitadelAuthClient zitadelAuthClient,
      ZitadelPatProvider patProvider,
      SubjectResolver subjectResolver,
      ChatService chatService,
      ChatJProperties properties,
      ChatUsersDirectory chatUsersDirectory,
      FeedbackMetrics feedbackMetrics,
      RoutingDistributionTracker routingDistributionTracker,
      FeedbackDistributionTracker feedbackDistributionTracker,
      PaymentSkillService paymentSkillService,
      ChatAnswerFinalizer answerFinalizer) {
    this.zitadelAuthClient = zitadelAuthClient;
    this.patProvider = patProvider;
    this.subjectResolver = subjectResolver;
    this.chatService = chatService;
    this.properties = properties;
    this.chatUsersDirectory = chatUsersDirectory;
    this.feedbackMetrics = feedbackMetrics;
    this.routingDistributionTracker = routingDistributionTracker;
    this.feedbackDistributionTracker = feedbackDistributionTracker;
    this.paymentSkillService = paymentSkillService;
    this.answerFinalizer = answerFinalizer;
  }

  @GetMapping("/health")
  public Map<String, String> health() {
    return Map.of("status", "UP");
  }

  @GetMapping("/api/chat-users")
  public Map<String, Object> chatUsers() {
    return Map.of("users", chatUsersDirectory.listChatUsers());
  }

  @GetMapping("/api/routing-stats")
  public Map<String, Object> routingStats() {
    return routingDistributionTracker.snapshot();
  }

  @GetMapping("/api/feedback-stats")
  public Map<String, Object> feedbackStats() {
    return feedbackDistributionTracker.snapshot();
  }

  @PostMapping("/api/auth/login")
  public LoginResponse login(@RequestBody LoginRequest request) {
    if (!StringUtils.hasText(patProvider.get())) {
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "ZITADEL service PAT not configured");
    }
    if (request == null
        || !StringUtils.hasText(request.user_id())
        || !StringUtils.hasText(request.password())) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "user_id and password required");
    }
    try {
      String loginName = zitadelAuthClient.loginNameForUser(request.user_id().trim());
      SessionCredentials session = zitadelAuthClient.login(loginName, request.password());
      List<String> roles = List.of();
      List<String> audiences = List.of();
      try {
        Optional<DirectoryUser> user = chatUsersDirectory.findByUserId(session.userId());
        if (user.isPresent()) {
          roles = List.copyOf(user.get().roles());
          audiences = AudienceLabels.forRoles(roles);
        }
      } catch (Exception ex) {
        log.warn("could not resolve audiences for {}", session.userId(), ex);
      }
      return new LoginResponse(
          session.userId(), session.sessionId(), session.sessionToken(), roles, audiences);
    } catch (Exception ex) {
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "login failed: " + ex.getMessage(), ex);
    }
  }

  @PostMapping("/api/chat")
  public ChatResponse chat(
      @RequestBody ChatRequest request,
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestHeader(value = "X-Session-Id", required = false) String sessionId) {
    if (request == null || !StringUtils.hasText(request.message())) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "message required");
    }
    Subject subject = requireChatSubject(authorization, sessionId);
    return chatService.ask(request, subject);
  }

  @PostMapping("/api/chat/skills/create-payment/confirm")
  public ChatResponse confirmCreatePayment(
      @RequestBody SkillConfirmRequest request,
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestHeader(value = "X-Session-Id", required = false) String sessionId) {
    return confirmSkill("create_payment", request, authorization, sessionId);
  }

  @PostMapping("/api/chat/skills/submit-payment/confirm")
  public ChatResponse confirmSubmitPayment(
      @RequestBody SkillConfirmRequest request,
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestHeader(value = "X-Session-Id", required = false) String sessionId) {
    return confirmSkill("submit_payment", request, authorization, sessionId);
  }

  @PostMapping("/api/chat/skills/approve-payment/confirm")
  public ChatResponse confirmApprovePayment(
      @RequestBody SkillConfirmRequest request,
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestHeader(value = "X-Session-Id", required = false) String sessionId) {
    return confirmSkill("approve_payment", request, authorization, sessionId);
  }

  @PostMapping("/api/chat/skills/cancel-payment/confirm")
  public ChatResponse confirmCancelPayment(
      @RequestBody SkillConfirmRequest request,
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestHeader(value = "X-Session-Id", required = false) String sessionId) {
    return confirmSkill("cancel_payment", request, authorization, sessionId);
  }

  private ChatResponse confirmSkill(
      String skill, SkillConfirmRequest request, String authorization, String sessionId) {
    if (request == null || !StringUtils.hasText(request.pending_id())) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "pending_id required");
    }
    Subject subject = requireChatSubject(authorization, sessionId);
    SkillRunResult result =
        paymentSkillService.confirm(skill, request.pending_id(), request.decision(), subject);
    return answerFinalizer.of(
        "confirm " + skill,
        "payments",
        result.answer(),
        "skill",
        "formatter",
        null,
        0.0,
        0.0,
        result.intentId(),
        null,
        List.of(),
        "none",
        List.of(),
        result.activities(),
        null);
  }

  @PostMapping("/api/chat/feedback")
  public Map<String, String> chatFeedback(
      @RequestBody ChatFeedbackRequest request,
      @RequestHeader(value = "Authorization", required = false) String authorization,
      @RequestHeader(value = "X-Session-Id", required = false) String sessionId) {
    Subject subject = requireChatSubject(authorization, sessionId);
    if (request == null
        || !StringUtils.hasText(request.rating())
        || !FEEDBACK_RATINGS.contains(request.rating())
        || !StringUtils.hasText(request.mode())
        || !StringUtils.hasText(request.path())
        || !StringUtils.hasText(request.cypher_provenance())
        || !StringUtils.hasText(request.answer_synthesis())) {
      throw new ResponseStatusException(
          HttpStatus.BAD_REQUEST,
          "rating (up|down), mode, path, cypher_provenance, answer_synthesis required");
    }
    ChatFeedbackContext feedback =
        ChatFeedbackContext.fromPayload(
            request.rating(),
            request.mode(),
            request.path(),
            request.cypher_provenance(),
            request.answer_synthesis(),
            request.retrieval_strategy(),
            subject.userId(),
            request.intent_id(),
            request.question_hash());
    feedbackMetrics.record(feedback);
    return Map.of("status", "recorded");
  }

  private Subject requireChatSubject(String authorization, String sessionId) {
    String bearer = extractBearer(authorization);
    Subject subject = subjectResolver.resolve(bearer, sessionId);
    if (!AppConfig.hasChatRole(subject.roles(), properties.chatRoles())) {
      throw new ResponseStatusException(
          HttpStatus.FORBIDDEN,
          "Chat requires COMPLIANCE_ANALYST, PAYMENT_CREATOR, FUNDING_APPROVER, "
              + "INSTRUCTION_CREATOR, or INSTRUCTION_APPROVER");
    }
    return subject;
  }

  private static String extractBearer(String authorization) {
    if (!StringUtils.hasText(authorization) || !authorization.toLowerCase().startsWith("bearer ")) {
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authorization Bearer token required");
    }
    return authorization.substring(7).trim();
  }
}
