package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentClientException;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentDeniedException;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentNotFoundException;
import java.nio.charset.StandardCharsets;
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
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

@ExtendWith(MockitoExtension.class)
class PaymentMutationClientTest {

  @Mock RestTemplate restTemplate;
  @Mock ServiceIdentity serviceIdentity;

  private PaymentMutationClient client;

  @BeforeEach
  void setUp() {
    client = new PaymentMutationClient(restTemplate, TestFixtures.properties(), serviceIdentity);
    when(serviceIdentity.oboHeaders(anyString(), anyString())).thenReturn(Map.of("Authorization", "Bearer svc"));
  }

  private void respondOk(Map<String, Object> body) {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenReturn(ResponseEntity.ok(body));
  }

  @Test
  void createSubmitApproveCancelReturnBody() {
    respondOk(Map.of("payment_id", "20260720-FICC-P-9", "status", "DRAFT"));
    assertEquals(
        "20260720-FICC-P-9",
        client.createPayment("20260720-FICC-I-1", 1_000_000d, "2026-07-21", "tok", "sess").get("payment_id"));
    assertEquals("DRAFT", client.submitPayment("20260720-FICC-P-9", "tok", "sess").get("status"));
    assertEquals("DRAFT", client.approvePayment("20260720-FICC-P-9", "tok", "sess").get("status"));
    assertEquals("DRAFT", client.cancelPayment("20260720-FICC-P-9", "tok", "sess").get("status"));
  }

  @Test
  void forbiddenMapsToPaymentDenied() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenThrow(
            new RestClientResponseException(
                "Forbidden", 403, "Forbidden", null,
                "{\"detail\":\"four-eyes violation\"}".getBytes(StandardCharsets.UTF_8), null));

    PaymentDeniedException ex =
        assertThrows(
            PaymentDeniedException.class,
            () -> client.submitPayment("20260720-FICC-P-9", "tok", "sess"));
    assertEquals("four-eyes violation", ex.detail());
  }

  @Test
  void notFoundMapsToPaymentNotFound() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenThrow(new RestClientResponseException("Not Found", 404, "Not Found", null, null, null));

    assertThrows(
        PaymentNotFoundException.class,
        () -> client.approvePayment("20260720-FICC-P-9", "tok", "sess"));
  }

  @Test
  void otherStatusMapsToPaymentClientException() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenThrow(new RestClientResponseException("Server Error", 500, "err", null, null, null));

    assertThrows(
        PaymentClientException.class,
        () -> client.cancelPayment("20260720-FICC-P-9", "tok", "sess"));
  }

  @Test
  void transportErrorMapsToPaymentClientException() {
    when(restTemplate.exchange(
            anyString(),
            eq(HttpMethod.POST),
            any(HttpEntity.class),
            any(ParameterizedTypeReference.class)))
        .thenThrow(new RestClientException("connection refused"));

    assertThrows(
        PaymentClientException.class,
        () -> client.createPayment("20260720-FICC-I-1", 1_000_000d, "2026-07-21", "tok", "sess"));
  }
}
