package com.sanjuthomas.policypilot.eligibility;

import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.util.UriUtils;

@Component
public class EligibilityClient {

  private final RestTemplate restTemplate;
  private final ChatJProperties properties;
  private final ServiceIdentity serviceIdentity;

  public EligibilityClient(
      RestTemplate restTemplate, ChatJProperties properties, ServiceIdentity serviceIdentity) {
    this.restTemplate = restTemplate;
    this.properties = properties;
    this.serviceIdentity = serviceIdentity;
  }

  public Map<String, Object> eligibleApproversForPayment(
      String paymentId, String userBearerToken, String userSessionId) {
    String url =
        trimSlash(properties.paymentServiceUrl())
            + "/api/v1/payments/"
            + paymentId
            + "/eligible-approvers";
    return postEmpty(url, userBearerToken, userSessionId, "payment service error: ");
  }

  public Map<String, Object> eligibleApproversForInstruction(
      String instructionId, String userBearerToken, String userSessionId) {
    String url =
        trimSlash(properties.instructionServiceUrl())
            + "/api/v1/instructions/"
            + instructionId
            + "/eligible-approvers";
    return postEmpty(url, userBearerToken, userSessionId, "instruction service error: ");
  }

  /**
   * Load payment (+ instruction) then call authorization-service eligible-submitters (parity with
   * Python {@code EligibilityClient.eligible_submitters_for_payment}).
   */
  public Map<String, Object> eligibleSubmittersForPayment(
      String paymentId, String userBearerToken, String userSessionId) {
    HttpHeaders headers = oboHeaders(userBearerToken, userSessionId);

    Map<String, Object> payment =
        getJson(
            trimSlash(properties.paymentServiceUrl()) + "/api/v1/payments/" + paymentId,
            headers,
            "payment service error: ");

    String instructionId = str(payment.get("instruction_id"));
    String instructionStatus = "";
    String instructionEndDate = "";
    if (StringUtils.hasText(instructionId)) {
      try {
        Map<String, Object> instruction =
            getJson(
                trimSlash(properties.instructionServiceUrl())
                    + "/api/v1/instructions/"
                    + instructionId,
                headers,
                "instruction service error: ");
        instructionStatus = str(instruction.get("status"));
        instructionEndDate = str(instruction.get("end_date"));
      } catch (ResponseStatusException ex) {
        if (ex.getStatusCode() != HttpStatus.UNAUTHORIZED
            && ex.getStatusCode() != HttpStatus.FORBIDDEN
            && ex.getStatusCode() != HttpStatus.NOT_FOUND) {
          throw ex;
        }
        // Match Python: ignore 401/403/404 on instruction load.
      }
    }

    @SuppressWarnings("unchecked")
    Map<String, Object> createdBy =
        payment.get("created_by") instanceof Map<?, ?> map
            ? (Map<String, Object>) map
            : Map.of();

    Map<String, Object> paymentPayload = new HashMap<>();
    paymentPayload.put(
        "payment_id",
        StringUtils.hasText(str(payment.get("payment_id")))
            ? payment.get("payment_id")
            : paymentId);
    paymentPayload.put("instruction_id", instructionId);
    paymentPayload.put(
        "instruction_version",
        payment.get("instruction_version") != null ? payment.get("instruction_version") : 1);
    paymentPayload.put(
        "status",
        StringUtils.hasText(str(payment.get("status"))) ? payment.get("status") : "DRAFT");
    paymentPayload.put("amount", payment.get("amount"));
    paymentPayload.put("currency", payment.get("currency"));
    paymentPayload.put("owning_lob", payment.get("owning_lob"));
    paymentPayload.put(
        "instruction_type",
        payment.get("instruction_type") != null ? payment.get("instruction_type") : "");
    paymentPayload.put("created_by_user_id", str(createdBy.get("user_id")));
    paymentPayload.put("created_by_supervisor_id", createdBy.get("supervisor_id"));

    Map<String, Object> body = new HashMap<>();
    body.put("payment", paymentPayload);
    body.put("instruction_status", instructionStatus);
    body.put("instruction_end_date", instructionEndDate);

    String authzUrl =
        trimSlash(properties.authorizationServiceUrl())
            + "/api/v1/authorization/payments/eligible-submitters";
    return postJson(authzUrl, body, headers, "authorization service error: ");
  }

  /** OPA club ceilings + absolute limit via authorization-service. */
  public Map<String, Object> paymentAmountLimits(String userBearerToken, String userSessionId) {
    String url =
        trimSlash(properties.authorizationServiceUrl())
            + "/api/v1/authorization/payment-amount-limits";
    return getJson(url, oboHeaders(userBearerToken, userSessionId), "authorization service error: ");
  }

  /** Normative OPA policy summary (domain + action) via authorization-service. */
  public Map<String, Object> policySummary(
      String domain, String action, String userBearerToken, String userSessionId) {
    String resolvedDomain =
        StringUtils.hasText(domain) ? domain.strip().toLowerCase() : "payment";
    String resolvedAction =
        StringUtils.hasText(action) ? action.strip().toUpperCase() : "APPROVE";
    String url =
        trimSlash(properties.authorizationServiceUrl())
            + "/api/v1/authorization/policy-summary?domain="
            + UriUtils.encodeQueryParam(resolvedDomain, StandardCharsets.UTF_8)
            + "&action="
            + UriUtils.encodeQueryParam(resolvedAction, StandardCharsets.UTF_8);
    return getJson(url, oboHeaders(userBearerToken, userSessionId), "authorization service error: ");
  }

  /**
   * ZITADEL group members via authorization-service, optionally filtered by role / covering LOB.
   */
  public Map<String, Object> groupMembers(
      String group,
      String userBearerToken,
      String userSessionId,
      String role,
      String coveringLob) {
    StringBuilder url =
        new StringBuilder(
            trimSlash(properties.authorizationServiceUrl())
                + "/api/v1/authorization/groups/"
                + UriUtils.encodePathSegment(group, StandardCharsets.UTF_8)
                + "/members");
    List<String> params = new ArrayList<>();
    if (StringUtils.hasText(role)) {
      params.add("role=" + UriUtils.encodeQueryParam(role, StandardCharsets.UTF_8));
    }
    if (StringUtils.hasText(coveringLob)) {
      params.add(
          "covering_lob=" + UriUtils.encodeQueryParam(coveringLob, StandardCharsets.UTF_8));
    }
    if (!params.isEmpty()) {
      url.append('?').append(String.join("&", params));
    }
    return getJson(
        url.toString(), oboHeaders(userBearerToken, userSessionId), "authorization service error: ");
  }

  /**
   * List payments visible to the OBO subject (e.g. {@code status=SUBMITTED} for approver worklist).
   */
  public List<Map<String, Object>> listPayments(
      String status, int limit, String userBearerToken, String userSessionId) {
    StringBuilder url =
        new StringBuilder(trimSlash(properties.paymentServiceUrl()) + "/api/v1/payments?");
    List<String> params = new ArrayList<>();
    if (StringUtils.hasText(status)) {
      params.add("status=" + UriUtils.encodeQueryParam(status.strip(), StandardCharsets.UTF_8));
    }
    params.add("limit=" + Math.max(1, Math.min(limit, 500)));
    url.append(String.join("&", params));
    return getJsonList(
        url.toString(),
        oboHeaders(userBearerToken, userSessionId),
        "payment service error: ");
  }

  private List<Map<String, Object>> getJsonList(
      String url, HttpHeaders headers, String errorPrefix) {
    try {
      ResponseEntity<List<Map<String, Object>>> response =
          restTemplate.exchange(
              url,
              HttpMethod.GET,
              new HttpEntity<>(headers),
              new ParameterizedTypeReference<>() {});
      return response.getBody() == null ? List.of() : response.getBody();
    } catch (RestClientResponseException ex) {
      throw mapHttpError(ex, errorPrefix);
    }
  }

  private Map<String, Object> postEmpty(
      String url, String userBearerToken, String userSessionId, String errorPrefix) {
    return postJson(url, null, oboHeaders(userBearerToken, userSessionId), errorPrefix);
  }

  private Map<String, Object> getJson(String url, HttpHeaders headers, String errorPrefix) {
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(
              url,
              HttpMethod.GET,
              new HttpEntity<>(headers),
              new ParameterizedTypeReference<>() {});
      return response.getBody() == null ? Map.of() : response.getBody();
    } catch (RestClientResponseException ex) {
      throw mapHttpError(ex, errorPrefix);
    }
  }

  private Map<String, Object> postJson(
      String url, Object body, HttpHeaders headers, String errorPrefix) {
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(
              url,
              HttpMethod.POST,
              new HttpEntity<>(body, headers),
              new ParameterizedTypeReference<>() {});
      return response.getBody() == null ? Map.of() : response.getBody();
    } catch (RestClientResponseException ex) {
      throw mapHttpError(ex, errorPrefix);
    }
  }

  private HttpHeaders oboHeaders(String userBearerToken, String userSessionId) {
    HttpHeaders headers = new HttpHeaders();
    serviceIdentity.oboHeaders(userBearerToken, userSessionId).forEach(headers::set);
    return headers;
  }

  private static ResponseStatusException mapHttpError(
      RestClientResponseException ex, String errorPrefix) {
    String detail = ex.getResponseBodyAsString();
    int status = ex.getStatusCode().value();
    if (status == 401) {
      return new ResponseStatusException(
          HttpStatus.UNAUTHORIZED, "authentication required — sign in to PolicyPilot");
    }
    if (status == 403) {
      return new ResponseStatusException(
          HttpStatus.FORBIDDEN, detail.isBlank() ? "not authorized for this question" : detail);
    }
    if (status == 404) {
      return new ResponseStatusException(HttpStatus.NOT_FOUND, detail);
    }
    return new ResponseStatusException(HttpStatus.BAD_GATEWAY, errorPrefix + detail, ex);
  }

  private static String trimSlash(String url) {
    return url == null ? "" : url.replaceAll("/$", "");
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }
}
