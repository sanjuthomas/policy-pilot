package com.policypilot.chatj.auth;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

@Component
public class SubjectResolver {

  private static final ObjectMapper MAPPER = new ObjectMapper();

  private final ZitadelAuthClient zitadelAuthClient;

  public SubjectResolver(ZitadelAuthClient zitadelAuthClient) {
    this.zitadelAuthClient = zitadelAuthClient;
  }

  public Subject resolve(String bearerToken, String sessionId) {
    if (!StringUtils.hasText(bearerToken)) {
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authorization Bearer token required");
    }
    if (!StringUtils.hasText(sessionId)) {
      throw new ResponseStatusException(
          HttpStatus.UNAUTHORIZED, "X-Session-Id required for session-token auth (M1)");
    }
    try {
      Map<String, Object> payload = zitadelAuthClient.getSession(sessionId, bearerToken);
      Object sessionObj = payload.get("session");
      if (!(sessionObj instanceof Map<?, ?> session)) {
        throw new IllegalStateException("session response missing session");
      }
      Object factorsObj = session.get("factors");
      if (!(factorsObj instanceof Map<?, ?> factors)) {
        throw new IllegalStateException("session response missing factors");
      }
      Object userObj = factors.get("user");
      if (!(userObj instanceof Map<?, ?> user)) {
        throw new IllegalStateException("session response missing user");
      }
      String zitadelUserId = stringVal(user.get("id"));
      if (!StringUtils.hasText(zitadelUserId)) {
        throw new IllegalStateException("session response missing user id");
      }
      Map<String, String> metadata = zitadelAuthClient.fetchUserMetadata(zitadelUserId);
      String fallback = stringVal(user.get("loginName"));
      Subject subject = fromMetadata(metadata, fallback);
      return subject.withTokens(bearerToken, sessionId);
    } catch (ResponseStatusException ex) {
      throw ex;
    } catch (Exception ex) {
      throw new ResponseStatusException(
          HttpStatus.UNAUTHORIZED, "could not resolve user from session token: " + ex.getMessage(), ex);
    }
  }

  static Subject fromMetadata(Map<String, String> metadata, String fallbackUserId) {
    String userId = firstNonBlank(metadata.get("subject_user_id"), fallbackUserId);
    if (!StringUtils.hasText(userId)) {
      throw new IllegalArgumentException("missing subject_user_id");
    }
    String title = metadata.get("title");
    if (!StringUtils.hasText(title)) {
      throw new IllegalArgumentException("missing title metadata");
    }
    String rolesRaw = metadata.get("roles");
    if (!StringUtils.hasText(rolesRaw)) {
      throw new IllegalArgumentException("missing roles metadata");
    }
    List<String> roles = parseJsonList(rolesRaw);
    if (roles.isEmpty()) {
      throw new IllegalArgumentException("roles claim is empty or invalid");
    }
    List<String> groups =
        StringUtils.hasText(metadata.get("groups"))
            ? parseJsonList(metadata.get("groups"))
            : List.of();
    List<String> coveringLobs =
        StringUtils.hasText(metadata.get("covering_lobs"))
            ? parseJsonList(metadata.get("covering_lobs"))
            : List.of();
    return new Subject(
        userId.contains("@") ? userId.split("@", 2)[0] : userId,
        metadata.get("given_name"),
        metadata.get("family_name"),
        title,
        metadata.get("lob"),
        roles,
        groups,
        metadata.get("supervisor_id"),
        coveringLobs,
        null,
        null);
  }

  private static List<String> parseJsonList(String raw) {
    try {
      List<String> parsed = MAPPER.readValue(raw, new TypeReference<>() {});
      return parsed == null ? List.of() : parsed;
    } catch (Exception ex) {
      String[] parts = raw.split(",");
      java.util.ArrayList<String> out = new java.util.ArrayList<>();
      for (String part : parts) {
        String trimmed = part.trim();
        if (!trimmed.isEmpty()) {
          out.add(trimmed);
        }
      }
      return Collections.unmodifiableList(out);
    }
  }

  private static String stringVal(Object value) {
    return value == null ? null : String.valueOf(value);
  }

  private static String firstNonBlank(String a, String b) {
    if (StringUtils.hasText(a)) {
      return a;
    }
    return b;
  }
}
