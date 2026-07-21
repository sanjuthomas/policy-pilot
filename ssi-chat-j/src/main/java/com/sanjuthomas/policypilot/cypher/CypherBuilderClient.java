package com.sanjuthomas.policypilot.cypher;

import com.sanjuthomas.policypilot.config.ChatJProperties;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanRequest;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateRequest;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/** HTTP client for cypher-builder-svc (:8097). */
@Component
public class CypherBuilderClient {

  private final RestTemplate restTemplate;
  private final String baseUrl;

  public CypherBuilderClient(RestTemplate restTemplate, ChatJProperties properties) {
    this.restTemplate = restTemplate;
    this.baseUrl = trimSlash(properties.cypherBuilderServiceUrl());
  }

  public PlanResponse plan(String question, String mode) {
    String url = baseUrl + "/v1/plan";
    PlanRequest body = new PlanRequest(question, mode == null || mode.isBlank() ? "events" : mode);
    PlanResponse response = restTemplate.postForObject(url, body, PlanResponse.class);
    if (response == null) {
      throw new IllegalStateException("cypher-builder-svc /v1/plan returned empty body");
    }
    return response;
  }

  public ValidateResponse validate(String cypher) {
    String url = baseUrl + "/v1/validate";
    ValidateResponse response =
        restTemplate.postForObject(url, new ValidateRequest(cypher), ValidateResponse.class);
    if (response == null) {
      throw new IllegalStateException("cypher-builder-svc /v1/validate returned empty body");
    }
    return response;
  }

  private static String trimSlash(String url) {
    if (url == null || url.isBlank()) {
      return "http://localhost:8097";
    }
    return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
  }
}
