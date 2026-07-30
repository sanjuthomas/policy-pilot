package com.sanjuthomas.policypilot.observability;

import com.sanjuthomas.policypilot.auth.Subject;
import org.slf4j.MDC;

/** Request-scoped MDC keys for structured chat logs (no tokens / question text). */
public final class ChatLogContext {

  public static final String REQUEST_ID = "request_id";
  public static final String USER_ID = "user_id";
  public static final String CHAT_MODE = "chat.mode";
  public static final String HTTP_ROUTE = "http.route";

  private ChatLogContext() {}

  public static void putSubject(Subject subject, String mode) {
    if (subject != null && subject.userId() != null && !subject.userId().isBlank()) {
      MDC.put(USER_ID, subject.userId().strip());
    }
    if (mode != null && !mode.isBlank()) {
      MDC.put(CHAT_MODE, mode.strip());
    }
  }

  public static void clearSubject() {
    MDC.remove(USER_ID);
    MDC.remove(CHAT_MODE);
  }

  public static void clearAll() {
    MDC.remove(REQUEST_ID);
    MDC.remove(USER_ID);
    MDC.remove(CHAT_MODE);
    MDC.remove(HTTP_ROUTE);
  }
}
