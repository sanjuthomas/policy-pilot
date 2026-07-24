package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.AuthzEvaluateException;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

@ExtendWith(MockitoExtension.class)
class AuthzPaymentEvaluateClientTest {

  @Mock RestTemplate restTemplate;
  @Mock ServiceIdentity serviceIdentity;

  private AuthzPaymentEvaluateClient client;

  private static Subject subject() {
    return new Subject(
        "pay-101", "Emily", "Rodriguez", "Analyst", "FICC",
        List.of("PAYMENT_CREATOR"), List.of("MIDDLE_OFFICE"), "sup-1", List.of("FX"), "tok", "sess");
  }

  @BeforeEach
  void setUp() {
    client = new AuthzPaymentEvaluateClient(restTemplate, TestFixtures.properties(), serviceIdentity);
    when(serviceIdentity.oboHeaders(anyString(), anyString())).thenReturn(Map.of("Authorization", "Bearer svc"));
  }

  @Test
  void evaluateReturnsDecisionFromBody() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenReturn(
            ResponseEntity.ok(
                Map.of(
                    "allowed", true,
                    "allow_basis", List.of("role PAYMENT_CREATOR"),
                    "violations", List.of())));

    PolicyDecision decision =
        client.evaluate("CREATE", Map.of("payment_id", "X"), "APPROVED", "2027-07-20", subject());

    assertTrue(decision.allowed());
    assertEquals(List.of("role PAYMENT_CREATOR"), decision.allowBasis());
  }

  @Test
  void evaluateReturnsDeniedWhenNotAllowed() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenReturn(
            ResponseEntity.ok(Map.of("allowed", false, "violations", List.of("four-eyes"))));

    PolicyDecision decision =
        client.evaluate("APPROVE", Map.of("payment_id", "X"), "APPROVED", "2027-07-20", subject());

    assertFalse(decision.allowed());
    assertEquals(List.of("four-eyes"), decision.violations());
  }

  @Test
  void evaluateWrapsClientErrors() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenThrow(new RestClientException("boom"));

    assertThrows(
        AuthzEvaluateException.class,
        () -> client.evaluate("CREATE", Map.of(), "APPROVED", "2027-07-20", subject()));
  }
}
