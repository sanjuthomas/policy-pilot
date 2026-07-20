package com.policypilot.chatj.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;
import org.springframework.ui.ConcurrentModel;

class HomeControllerTest {

  private final HomeController controller = new HomeController();

  @Test
  void homeAddsModelAttributes() {
    ConcurrentModel model = new ConcurrentModel();
    assertEquals("index", controller.home(model));
    assertEquals("ssi-chat-j", model.getAttribute("serviceName"));
    assertEquals(8096, model.getAttribute("port"));
  }

  @Test
  void indexIntegrityStubDisablesBanner() {
    var body = controller.indexIntegrityStub();
    assertEquals(false, body.get("show_banner"));
    assertEquals(null, body.get("banner_message"));
  }
}
