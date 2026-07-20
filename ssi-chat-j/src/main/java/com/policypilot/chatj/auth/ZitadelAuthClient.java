package com.policypilot.chatj.auth;

import com.policypilot.chatj.config.AppConfig.ZitadelPatProvider;
import com.policypilot.chatj.config.ChatJProperties;
import java.net.URI;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

@Component
public class ZitadelAuthClient {

  private final RestTemplate restTemplate;
  private final ChatJProperties properties;
  private final ZitadelPatProvider patProvider;

  public ZitadelAuthClient(
      RestTemplate restTemplate, ChatJProperties properties, ZitadelPatProvider patProvider) {
    this.restTemplate = restTemplate;
    this.properties = properties;
    this.patProvider = patProvider;
  }

  public SessionCredentials login(String loginName, String password) {
    List<String> candidates = new java.util.ArrayList<>();
    candidates.add(loginName);
    if (loginName.contains("@")) {
      candidates.add(loginName.split("@", 2)[0]);
    }
    Exception last = null;
    for (String candidate : candidates) {
      try {
        return createSession(candidate, password);
      } catch (Exception ex) {
        last = ex;
      }
    }
    if (last instanceof RuntimeException runtime) {
      throw runtime;
    }
    throw new IllegalStateException("login failed", last);
  }

  public String loginNameForUser(String userId) {
    if (userId.contains("@")) {
      return userId;
    }
    return userId + "@" + properties.emailDomain();
  }

  @SuppressWarnings("unchecked")
  private SessionCredentials createSession(String loginName, String password) {
    Map<String, Object> body = new HashMap<>();
    body.put(
        "checks",
        Map.of(
            "user", Map.of("loginName", loginName),
            "password", Map.of("password", password)));

    ResponseEntity<Map> response =
        restTemplate.exchange(
            URI.create(zitadelBase() + "/v2/sessions"),
            HttpMethod.POST,
            new HttpEntity<>(body, serviceHeaders()),
            Map.class);

    Map<String, Object> payload = response.getBody();
    if (payload == null) {
      throw new IllegalStateException("empty ZITADEL session response");
    }
    String sessionId = stringVal(payload, "sessionId", "session_id");
    String sessionToken = stringVal(payload, "sessionToken", "session_token");
    if (!StringUtils.hasText(sessionId) || !StringUtils.hasText(sessionToken)) {
      throw new IllegalStateException("ZITADEL session response missing session fields: " + payload);
    }
    String userId = loginName.contains("@") ? loginName.split("@", 2)[0] : loginName;
    return new SessionCredentials(sessionId, sessionToken, userId);
  }

  public Map<String, Object> getSession(String sessionId, String sessionToken) {
    HttpHeaders headers = serviceHeaders();
    headers.setAccept(List.of(MediaType.APPLICATION_JSON));
    String url =
        zitadelBase()
            + "/v2/sessions/"
            + sessionId
            + "?sessionToken="
            + java.net.URLEncoder.encode(sessionToken, java.nio.charset.StandardCharsets.UTF_8);
    ResponseEntity<Map> response =
        restTemplate.exchange(URI.create(url), HttpMethod.GET, new HttpEntity<>(headers), Map.class);
    return response.getBody() == null ? Map.of() : response.getBody();
  }

  public Map<String, String> fetchUserMetadata(String zitadelUserId) {
    String pat = patProvider.get();
    if (!StringUtils.hasText(pat)) {
      throw new IllegalStateException("zitadel service PAT is not configured");
    }
    ResponseEntity<Map> response =
        restTemplate.exchange(
            URI.create(zitadelBase() + "/v2/users/" + zitadelUserId + "/metadata/search"),
            HttpMethod.POST,
            new HttpEntity<>(Map.of(), serviceHeaders()),
            Map.class);
    Map<String, Object> payload = response.getBody() == null ? Map.of() : response.getBody();
    Map<String, String> metadata = new HashMap<>();
    Object rawList = payload.get("metadata");
    if (rawList instanceof List<?> entries) {
      for (Object entry : entries) {
        if (entry instanceof Map<?, ?> map) {
          Object key = map.get("key");
          Object value = map.get("value");
          if (key instanceof String k && value instanceof String v) {
            metadata.put(k, decodeMetadataValue(v));
          }
        }
      }
    }
    return metadata;
  }

  String zitadelBase() {
    if (StringUtils.hasText(properties.zitadelInternalUrl())) {
      return properties.zitadelInternalUrl().replaceAll("/$", "");
    }
    return properties.zitadelUrl().replaceAll("/$", "");
  }

  HttpHeaders serviceHeaders() {
    HttpHeaders headers = new HttpHeaders();
    headers.setBearerAuth(patProvider.get());
    headers.setContentType(MediaType.APPLICATION_JSON);
    headers.setAccept(List.of(MediaType.APPLICATION_JSON));
    if (StringUtils.hasText(properties.zitadelHostHeader())) {
      headers.set(HttpHeaders.HOST, properties.zitadelHostHeader());
    } else if (StringUtils.hasText(properties.oidcIssuerUrl())) {
      try {
        String host = URI.create(properties.oidcIssuerUrl()).getHost();
        if (StringUtils.hasText(host)) {
          headers.set(HttpHeaders.HOST, host);
        }
      } catch (Exception ignored) {
        // leave Host unset
      }
    }
    return headers;
  }

  private static String stringVal(Map<String, Object> map, String primary, String alt) {
    Object value = map.get(primary);
    if (value == null) {
      value = map.get(alt);
    }
    return value == null ? null : String.valueOf(value);
  }

  static String decodeMetadataValue(String value) {
    try {
      return new String(java.util.Base64.getDecoder().decode(value), java.nio.charset.StandardCharsets.UTF_8);
    } catch (IllegalArgumentException ex) {
      return value;
    }
  }

  public static class LoginFailedException extends RuntimeException {
    public LoginFailedException(String message, Throwable cause) {
      super(message, cause);
    }
  }

  public static boolean isHttpUnauthorized(Exception ex) {
    return ex instanceof RestClientResponseException rce && rce.getStatusCode().value() == 401;
  }
}
