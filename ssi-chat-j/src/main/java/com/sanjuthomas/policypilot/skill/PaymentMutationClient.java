package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import com.sanjuthomas.policypilot.eligibility.HttpErrorBodies;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

/**
 * Payment mutations via svc-chat + user OBO. Mirrors Python
 * {@code chat_application.skills.payment_client.PaymentClient} create/submit/approve/cancel.
 */
@Component
public class PaymentMutationClient {

  /** Generic payment-service failure. */
  public static class PaymentClientException extends RuntimeException {
    public PaymentClientException(String message) {
      super(message);
    }
  }

  /** Payment mutation refused by policy (HTTP 403). Carries the detail for the answer. */
  public static class PaymentDeniedException extends PaymentClientException {
    private final String detail;

    public PaymentDeniedException(String detail) {
      super(detail);
      this.detail = detail;
    }

    public String detail() {
      return detail;
    }
  }

  /** Payment not found (HTTP 404). */
  public static class PaymentNotFoundException extends PaymentClientException {
    public PaymentNotFoundException(String message) {
      super(message);
    }
  }

  private final RestTemplate restTemplate;
  private final ChatJProperties properties;
  private final ServiceIdentity serviceIdentity;

  public PaymentMutationClient(
      RestTemplate restTemplate, ChatJProperties properties, ServiceIdentity serviceIdentity) {
    this.restTemplate = restTemplate;
    this.properties = properties;
    this.serviceIdentity = serviceIdentity;
  }

  public Map<String, Object> createPayment(
      String instructionId,
      double amount,
      String valueDate,
      String userBearerToken,
      String userSessionId) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("instruction_id", instructionId);
    body.put("amount", amount);
    body.put("value_date", valueDate);
    String url = trimSlash(properties.paymentServiceUrl()) + "/api/v1/payments";
    return post(url, body, userBearerToken, userSessionId, "CREATE");
  }

  public Map<String, Object> submitPayment(
      String paymentId, String userBearerToken, String userSessionId) {
    String url = trimSlash(properties.paymentServiceUrl()) + "/api/v1/payments/" + paymentId + "/submit";
    return post(url, null, userBearerToken, userSessionId, "SUBMIT");
  }

  public Map<String, Object> approvePayment(
      String paymentId, String userBearerToken, String userSessionId) {
    String url = trimSlash(properties.paymentServiceUrl()) + "/api/v1/payments/" + paymentId + "/approve";
    return post(url, null, userBearerToken, userSessionId, "APPROVE");
  }

  public Map<String, Object> cancelPayment(
      String paymentId, String userBearerToken, String userSessionId) {
    String url = trimSlash(properties.paymentServiceUrl()) + "/api/v1/payments/" + paymentId + "/cancel";
    return post(url, Map.of(), userBearerToken, userSessionId, "CANCEL");
  }

  private Map<String, Object> post(
      String url, Object body, String userBearerToken, String userSessionId, String action) {
    HttpHeaders headers = new HttpHeaders();
    serviceIdentity.oboHeaders(userBearerToken, userSessionId).forEach(headers::set);
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(
              url,
              HttpMethod.POST,
              new HttpEntity<>(body, headers),
              new ParameterizedTypeReference<>() {});
      return response.getBody() == null ? Map.of() : response.getBody();
    } catch (RestClientResponseException ex) {
      int status = ex.getStatusCode().value();
      String detail = HttpErrorBodies.detail(ex.getResponseBodyAsString());
      if (status == 403) {
        throw new PaymentDeniedException(detail.isBlank() ? "not authorized" : detail);
      }
      if (status == 404) {
        throw new PaymentNotFoundException("payment not found");
      }
      throw new PaymentClientException(
          "payment-service rejected " + action + " (" + status + "): " + detail);
    } catch (RestClientException ex) {
      throw new PaymentClientException("payment-service unreachable: " + ex.getMessage());
    }
  }

  private static String trimSlash(String url) {
    return url == null ? "" : url.replaceAll("/$", "");
  }
}
