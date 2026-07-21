package com.sanjuthomas.policypilot.eligibility;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.util.StringUtils;

/** Unwrap FastAPI-style {@code {"detail":"…"}} error bodies for chat-facing messages. */
public final class HttpErrorBodies {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  private HttpErrorBodies() {}

  /**
   * Prefer {@code detail} when the body is JSON; otherwise return the trimmed raw body (or empty).
   */
  public static String detail(String responseBody) {
    if (!StringUtils.hasText(responseBody)) {
      return "";
    }
    String trimmed = responseBody.strip();
    try {
      JsonNode root = MAPPER.readTree(trimmed);
      if (root != null && root.hasNonNull("detail")) {
        JsonNode detail = root.get("detail");
        if (detail.isTextual()) {
          return detail.asText().strip();
        }
        // FastAPI validation errors use detail as an array/object — keep compact JSON.
        return detail.toString();
      }
    } catch (Exception ignored) {
      // not JSON — use raw body
    }
    return trimmed;
  }
}
