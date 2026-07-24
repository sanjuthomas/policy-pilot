package com.sanjuthomas.policypilot.api;

import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

/**
 * Proxies ssi-indexer {@code GET /api/index-integrity} for the shared PolicyPilot integrity banner
 * (parity with Python chat).
 */
@Component
public class IndexIntegrityClient {

  private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
      new ParameterizedTypeReference<>() {};

  private final RestTemplate restTemplate;
  private final ChatJProperties properties;

  public IndexIntegrityClient(RestTemplate restTemplate, ChatJProperties properties) {
    this.restTemplate = restTemplate;
    this.properties = properties;
  }

  public Map<String, Object> fetchStatus() {
    String base = properties.indexerUrl();
    if (!StringUtils.hasText(base)) {
      return quiet("indexer url not configured");
    }
    String url = trimSlash(base) + "/api/index-integrity";
    try {
      ResponseEntity<Map<String, Object>> response =
          restTemplate.exchange(url, HttpMethod.GET, null, MAP_TYPE);
      if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
        return quiet("indexer status " + response.getStatusCode().value());
      }
      return response.getBody();
    } catch (RestClientResponseException ex) {
      return quiet("indexer status " + ex.getStatusCode().value());
    } catch (Exception ex) {
      return quiet(ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage());
    }
  }

  private static Map<String, Object> quiet(String error) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("show_banner", false);
    body.put("banner_message", null);
    body.put("error", error);
    return body;
  }

  private static String trimSlash(String url) {
    return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
  }
}
