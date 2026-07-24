package com.sanjuthomas.policypilot.api;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HomeController {

  private final IndexIntegrityClient indexIntegrityClient;

  public HomeController(IndexIntegrityClient indexIntegrityClient) {
    this.indexIntegrityClient = indexIntegrityClient;
  }

  @GetMapping("/api/index-integrity")
  public Map<String, Object> indexIntegrity() {
    return indexIntegrityClient.fetchStatus();
  }
}
