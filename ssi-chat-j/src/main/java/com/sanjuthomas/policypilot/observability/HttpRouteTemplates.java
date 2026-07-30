package com.sanjuthomas.policypilot.observability;

/** Low-cardinality HTTP route labels for metrics and MDC (no raw path params). */
public final class HttpRouteTemplates {

  private HttpRouteTemplates() {}

  public static String template(String path) {
    if (path == null || path.isBlank()) {
      return "unknown";
    }
    return switch (path) {
      case "/api/chat" -> "/api/chat";
      case "/api/chat/feedback" -> "/api/chat/feedback";
      case "/api/auth/login" -> "/api/auth/login";
      case "/api/chat-users" -> "/api/chat-users";
      case "/api/routing-stats" -> "/api/routing-stats";
      case "/api/feedback-stats" -> "/api/feedback-stats";
      case "/health" -> "/health";
      case "/api/chat/skills/create-payment/confirm",
          "/api/chat/skills/submit-payment/confirm",
          "/api/chat/skills/approve-payment/confirm",
          "/api/chat/skills/cancel-payment/confirm" -> "/api/chat/skills/*/confirm";
      default -> path.startsWith("/api/") ? "/api/*" : "other";
    };
  }
}
