package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.auth.ServiceIdentity;
import com.policypilot.chatj.config.ChatJProperties;
import java.util.List;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

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
        properties.paymentServiceUrl().replaceAll("/$", "")
            + "/api/v1/payments/"
            + paymentId
            + "/eligible-approvers";
    HttpHeaders headers = new HttpHeaders();
    serviceIdentity
        .oboHeaders(userBearerToken, userSessionId)
        .forEach(headers::set);
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(
              url,
              HttpMethod.POST,
              new HttpEntity<>(headers),
              new ParameterizedTypeReference<>() {});
      return response.getBody() == null ? Map.of() : response.getBody();
    } catch (RestClientResponseException ex) {
      String detail = ex.getResponseBodyAsString();
      int status = ex.getStatusCode().value();
      if (status == 401) {
        throw new ResponseStatusException(
            HttpStatus.UNAUTHORIZED, "authentication required — sign in to PolicyPilot");
      }
      if (status == 403) {
        throw new ResponseStatusException(
            HttpStatus.FORBIDDEN, detail.isBlank() ? "not authorized for this question" : detail);
      }
      if (status == 404) {
        throw new ResponseStatusException(HttpStatus.NOT_FOUND, detail);
      }
      throw new ResponseStatusException(
          HttpStatus.BAD_GATEWAY, "payment service error: " + detail, ex);
    }
  }
}
