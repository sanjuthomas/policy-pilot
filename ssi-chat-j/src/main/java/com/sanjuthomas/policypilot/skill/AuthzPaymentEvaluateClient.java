package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/**
 * Calls authorization-service {@code POST /api/v1/authorization/payments/evaluate} with service
 * identity + user OBO for lifecycle CREATE / SUBMIT / APPROVE / CANCEL dry-runs. Mirrors Python
 * {@code chat_application.authz.obo.AuthzOboClient.evaluate_payment}.
 */
@Component
public class AuthzPaymentEvaluateClient {

  /** Thrown when policy evaluation cannot complete (used for fail-closed recheck). */
  public static class AuthzEvaluateException extends RuntimeException {
    public AuthzEvaluateException(String message) {
      super(message);
    }

    public AuthzEvaluateException(String message, Throwable cause) {
      super(message, cause);
    }
  }

  /** OPA decision. */
  public record PolicyDecision(boolean allowed, List<String> allowBasis, List<String> violations) {
    public PolicyDecision {
      allowBasis = allowBasis == null ? List.of() : List.copyOf(allowBasis);
      violations = violations == null ? List.of() : List.copyOf(violations);
    }
  }

  private final RestTemplate restTemplate;
  private final ChatJProperties properties;
  private final ServiceIdentity serviceIdentity;

  public AuthzPaymentEvaluateClient(
      RestTemplate restTemplate, ChatJProperties properties, ServiceIdentity serviceIdentity) {
    this.restTemplate = restTemplate;
    this.properties = properties;
    this.serviceIdentity = serviceIdentity;
  }

  public PolicyDecision evaluate(
      String action,
      Map<String, Object> payment,
      String instructionStatus,
      String instructionEndDate,
      Subject subject) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("action", action);
    body.put("payment", payment);
    body.put("instruction_status", instructionStatus == null ? "" : instructionStatus);
    body.put("instruction_end_date", instructionEndDate == null ? "" : instructionEndDate);
    if (subject != null) {
      body.put("subject", subjectPayload(subject));
    }

    String url =
        trimSlash(properties.authorizationServiceUrl())
            + "/api/v1/authorization/payments/evaluate";
    HttpHeaders headers = new HttpHeaders();
    serviceIdentity
        .oboHeaders(subject == null ? null : subject.bearerToken(), subject == null ? null : subject.sessionId())
        .forEach(headers::set);
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(
              url,
              HttpMethod.POST,
              new HttpEntity<>(body, headers),
              new ParameterizedTypeReference<>() {});
      Map<String, Object> payload = response.getBody() == null ? Map.of() : response.getBody();
      return new PolicyDecision(
          asBoolean(payload.get("allowed")),
          asStringList(payload.get("allow_basis")),
          asStringList(payload.get("violations")));
    } catch (RestClientException ex) {
      throw new AuthzEvaluateException(
          "authorization-service rejected evaluate: " + ex.getMessage(), ex);
    }
  }

  static Map<String, Object> subjectPayload(Subject subject) {
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("user_id", subject.userId());
    payload.put("given_name", subject.givenName());
    payload.put("family_name", subject.familyName());
    payload.put("title", subject.title());
    payload.put("lob", subject.lob());
    payload.put("roles", subject.roles() == null ? List.of() : subject.roles());
    payload.put("groups", subject.groups() == null ? List.of() : subject.groups());
    payload.put("supervisor_id", subject.supervisorId());
    payload.put("covering_lobs", subject.coveringLobs() == null ? List.of() : subject.coveringLobs());
    return payload;
  }

  private static boolean asBoolean(Object value) {
    return value instanceof Boolean b && b;
  }

  private static List<String> asStringList(Object value) {
    List<String> out = new ArrayList<>();
    if (value instanceof List<?> list) {
      for (Object item : list) {
        if (item != null) {
          out.add(String.valueOf(item));
        }
      }
    }
    return out;
  }

  private static String trimSlash(String url) {
    return url == null ? "" : url.replaceAll("/$", "");
  }
}
