package com.sanjuthomas.policypilot.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

class HomeControllerTest {

  private final HomeController controller = new HomeController();

  @Test
  void indexIntegrityStubDisablesBanner() {
    var body = controller.indexIntegrityStub();
    assertEquals(false, body.get("show_banner"));
    assertNull(body.get("banner_message"));
  }
}
