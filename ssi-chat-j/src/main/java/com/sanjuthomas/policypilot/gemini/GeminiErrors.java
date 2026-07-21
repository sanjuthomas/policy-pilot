package com.sanjuthomas.policypilot.gemini;

/**
 * Detect vendor / Gemini capacity failures for user-facing retry UX (parity with Python {@code
 * chat_application.gemini.errors}).
 */
public final class GeminiErrors {

  public static final int RATE_LIMIT_RETRY_SECONDS = 30;

  public static final String RATE_LIMIT_INTENT_ID = "llm.rate_limited";

  public static final String RATE_LIMIT_ANSWER =
      "Google Gemini (our answer model) is temporarily under stress "
          + "(HTTP 429 · Resource Exhausted). "
          + "Vendor capacity recovered slowly — please wait about 30 seconds, "
          + "then retry the same question.";

  private GeminiErrors() {}

  /** True when {@code ex} (or a nested cause) looks like Vertex/Gemini HTTP 429. */
  public static boolean isRateLimit(Throwable ex) {
    Throwable current = ex;
    int depth = 0;
    while (current != null && depth < 16) {
      if (matchesMessage(current.getMessage())) {
        return true;
      }
      // gRPC StatusRuntimeException exposes getStatus().getCode()
      try {
        var statusMethod = current.getClass().getMethod("getStatus");
        Object status = statusMethod.invoke(current);
        if (status != null) {
          Object code = status.getClass().getMethod("getCode").invoke(status);
          if (code != null && "RESOURCE_EXHAUSTED".equalsIgnoreCase(String.valueOf(code))) {
            return true;
          }
          if (code != null && "429".equals(String.valueOf(code))) {
            return true;
          }
        }
      } catch (ReflectiveOperationException ignored) {
        // not a gRPC status-bearing type
      }
      current = current.getCause();
      depth++;
    }
    return false;
  }

  private static boolean matchesMessage(String message) {
    if (message == null || message.isBlank()) {
      return false;
    }
    String upper = message.toUpperCase();
    if (upper.contains("RESOURCE_EXHAUSTED")) {
      return true;
    }
    return upper.contains("429")
        && (upper.contains("RESOURCE") || upper.contains("QUOTA") || upper.contains("RATE"));
  }
}
