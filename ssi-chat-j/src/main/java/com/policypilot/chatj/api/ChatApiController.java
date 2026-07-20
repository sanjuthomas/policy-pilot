package com.policypilot.chatj.api;

import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.api.ApiModels.LoginRequest;
import com.policypilot.chatj.api.ApiModels.LoginResponse;
import com.policypilot.chatj.auth.ChatUsersDirectory;
import com.policypilot.chatj.auth.SessionCredentials;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.auth.SubjectResolver;
import com.policypilot.chatj.auth.ZitadelAuthClient;
import com.policypilot.chatj.config.AppConfig;
import com.policypilot.chatj.config.AppConfig.ZitadelPatProvider;
import com.policypilot.chatj.config.ChatJProperties;
import com.policypilot.chatj.service.ChatService;
import java.util.List;
import java.util.Map;
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

  private final ZitadelAuthClient zitadelAuthClient;
  private final ZitadelPatProvider patProvider;
  private final SubjectResolver subjectResolver;
  private final ChatService chatService;
  private final ChatJProperties properties;
  private final ChatUsersDirectory chatUsersDirectory;

  public ChatApiController(
      ZitadelAuthClient zitadelAuthClient,
      ZitadelPatProvider patProvider,
      SubjectResolver subjectResolver,
      ChatService chatService,
      ChatJProperties properties,
      ChatUsersDirectory chatUsersDirectory) {
    this.zitadelAuthClient = zitadelAuthClient;
    this.patProvider = patProvider;
    this.subjectResolver = subjectResolver;
    this.chatService = chatService;
    this.properties = properties;
    this.chatUsersDirectory = chatUsersDirectory;
  }

  @GetMapping("/health")
  public Map<String, String> health() {
    return Map.of("status", "UP");
  }

  @GetMapping("/api/chat-users")
  public Map<String, Object> chatUsers() {
    return Map.of("users", chatUsersDirectory.listChatUsers());
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
      return new LoginResponse(
          session.userId(), session.sessionId(), session.sessionToken(), List.of(), List.of());
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
    String bearer = extractBearer(authorization);
    Subject subject = subjectResolver.resolve(bearer, sessionId);
    if (!AppConfig.hasChatRole(subject.roles(), properties.chatRoles())) {
      throw new ResponseStatusException(
          HttpStatus.FORBIDDEN,
          "Chat requires COMPLIANCE_ANALYST, PAYMENT_CREATOR, FUNDING_APPROVER, "
              + "INSTRUCTION_CREATOR, or INSTRUCTION_APPROVER");
    }
    return chatService.ask(request, subject);
  }

  private static String extractBearer(String authorization) {
    if (!StringUtils.hasText(authorization) || !authorization.toLowerCase().startsWith("bearer ")) {
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authorization Bearer token required");
    }
    return authorization.substring(7).trim();
  }
}
