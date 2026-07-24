package com.sanjuthomas.policypilot.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.TestFixtures;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

class IndexIntegrityClientTest {

  private RestTemplate restTemplate;
  private IndexIntegrityClient client;

  @BeforeEach
  void setUp() {
    restTemplate = mock(RestTemplate.class);
    client = new IndexIntegrityClient(restTemplate, TestFixtures.properties());
  }

  @Test
  void fetchStatusReturnsIndexerBodyOnSuccess() {
    Map<String, Object> payload =
        Map.of("show_banner", true, "banner_message", "lag high", "kafka_lag_total", 99);
    when(restTemplate.exchange(
            eq("http://indexer:8090/api/index-integrity"),
            eq(HttpMethod.GET),
            eq(null),
            any(ParameterizedTypeReference.class)))
        .thenReturn(ResponseEntity.ok(payload));

    assertEquals(payload, client.fetchStatus());
  }

  @Test
  void fetchStatusQuietsOnHttpError() {
    when(restTemplate.exchange(
            eq("http://indexer:8090/api/index-integrity"),
            eq(HttpMethod.GET),
            eq(null),
            any(ParameterizedTypeReference.class)))
        .thenThrow(
            new RestClientResponseException("boom", 503, "Unavailable", null, null, null));

    Map<String, Object> body = client.fetchStatus();
    assertEquals(false, body.get("show_banner"));
    assertNull(body.get("banner_message"));
    assertEquals("indexer status 503", body.get("error"));
  }

  @Test
  void fetchStatusQuietsOnTransportError() {
    when(restTemplate.exchange(
            eq("http://indexer:8090/api/index-integrity"),
            eq(HttpMethod.GET),
            eq(null),
            any(ParameterizedTypeReference.class)))
        .thenThrow(new RestClientException("connection refused"));

    Map<String, Object> body = client.fetchStatus();
    assertEquals(false, body.get("show_banner"));
    assertEquals("connection refused", body.get("error"));
  }

  @Test
  void fetchStatusQuietsOnNonSuccessStatus() {
    when(restTemplate.exchange(
            eq("http://indexer:8090/api/index-integrity"),
            eq(HttpMethod.GET),
            eq(null),
            any(ParameterizedTypeReference.class)))
        .thenReturn(ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(null));

    Map<String, Object> body = client.fetchStatus();
    assertEquals(false, body.get("show_banner"));
    assertEquals("indexer status 502", body.get("error"));
  }
}
