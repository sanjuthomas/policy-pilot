package com.sanjuthomas.policypilot.api;

import java.util.HashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HomeController {

  @GetMapping("/api/index-integrity")
  public Map<String, Object> indexIntegrityStub() {
    // M1: no indexer wiring yet — keep UI banner quiet.
    HashMap<String, Object> body = new HashMap<>();
    body.put("show_banner", false);
    body.put("banner_message", null);
    return body;
  }
}
