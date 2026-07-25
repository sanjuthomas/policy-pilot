package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/**
 * Persists governed-activity audit executions on payment-service (business evidence; OPA lives on
 * security events and is linked, not duplicated).
 */
@Component
public class AuditExecutionClient {

  private static final Logger log = LoggerFactory.getLogger(AuditExecutionClient.class);

  private final RestTemplate restTemplate;
  private final ChatJProperties properties;
  private final ServiceIdentity serviceIdentity;

  public AuditExecutionClient(
      RestTemplate restTemplate, ChatJProperties properties, ServiceIdentity serviceIdentity) {
    this.restTemplate = restTemplate;
    this.properties = properties;
    this.serviceIdentity = serviceIdentity;
  }

  public String create(Map<String, Object> body, Subject subject) {
    String url = trimSlash(properties.paymentServiceUrl()) + "/api/v1/audit-executions";
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(
              url,
              HttpMethod.POST,
              new HttpEntity<>(body, oboHeaders(subject)),
              new ParameterizedTypeReference<>() {});
      Map<String, Object> payload = response.getBody() == null ? Map.of() : response.getBody();
      Object id = payload.get("execution_id");
      return id == null ? null : String.valueOf(id);
    } catch (RestClientException ex) {
      log.warn("audit execution create failed: {}", ex.toString());
      return null;
    }
  }

  public void patch(String executionId, Map<String, Object> body, Subject subject) {
    if (executionId == null || executionId.isBlank()) {
      return;
    }
    String url =
        trimSlash(properties.paymentServiceUrl()) + "/api/v1/audit-executions/" + executionId;
    try {
      restTemplate.exchange(
          url,
          HttpMethod.PATCH,
          new HttpEntity<>(body, oboHeaders(subject)),
          new ParameterizedTypeReference<Map<String, Object>>() {});
    } catch (RestClientException ex) {
      log.warn("audit execution patch failed executionId={}: {}", executionId, ex.toString());
    }
  }

  public static Map<String, Object> policyExchange(
      Map<String, Object> evaluateRequest, Map<String, Object> evaluateResponse) {
    Map<String, Object> exchange = new LinkedHashMap<>();
    exchange.put("evaluate_request", evaluateRequest == null ? Map.of() : evaluateRequest);
    exchange.put("evaluate_response", evaluateResponse == null ? Map.of() : evaluateResponse);
    return exchange;
  }

  public static Map<String, Object> timelineStep(
      String step, String summary, String decision, String atIso) {
    Map<String, Object> item = new LinkedHashMap<>();
    item.put("step", step);
    item.put("summary", summary);
    if (decision != null) {
      item.put("decision", decision);
    }
    if (atIso != null) {
      item.put("at", atIso);
    }
    return item;
  }

  public static List<Map<String, Object>> asTimeline(List<Map<String, Object>> steps) {
    return steps == null ? List.of() : List.copyOf(steps);
  }

  private HttpHeaders oboHeaders(Subject subject) {
    HttpHeaders headers = new HttpHeaders();
    serviceIdentity
        .oboHeaders(
            subject == null ? null : subject.bearerToken(),
            subject == null ? null : subject.sessionId())
        .forEach(headers::set);
    return headers;
  }

  private static String trimSlash(String url) {
    return url == null ? "" : url.replaceAll("/$", "");
  }
}
