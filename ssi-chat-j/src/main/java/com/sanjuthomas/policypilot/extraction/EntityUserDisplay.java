package com.sanjuthomas.policypilot.extraction;

import java.util.Map;
import org.springframework.util.StringUtils;

/** Shared UserReference → display string for document-extraction cards. */
public final class EntityUserDisplay {

  private static final String NOT_YET_APPROVED = "— (not yet approved)";

  private EntityUserDisplay() {}

  public static String creator(Object value) {
    return userDisplay(value, "—");
  }

  public static String approver(Object value) {
    String display = userDisplay(value, null);
    return display == null ? NOT_YET_APPROVED : display;
  }

  private static String userDisplay(Object value, String empty) {
    if (!(value instanceof Map<?, ?> map)) {
      return empty;
    }
    String userId = str(map.get("user_id")).strip();
    String given = str(map.get("given_name")).strip();
    String family = str(map.get("family_name")).strip();
    if (StringUtils.hasText(family) && StringUtils.hasText(given) && StringUtils.hasText(userId)) {
      return family + ", " + given + " (" + userId + ")";
    }
    if (StringUtils.hasText(userId)) {
      return userId;
    }
    return empty;
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }
}
