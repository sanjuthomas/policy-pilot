package com.sanjuthomas.policypilot.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.Map;
import org.junit.jupiter.api.Test;

class HomeControllerTest {

  @Test
  void indexIntegrityDelegatesToClient() {
    IndexIntegrityClient client = mock(IndexIntegrityClient.class);
    Map<String, Object> payload = Map.of("show_banner", true, "banner_message", "behind");
    when(client.fetchStatus()).thenReturn(payload);

    HomeController controller = new HomeController(client);
    assertSame(payload, controller.indexIntegrity());
    assertEquals(true, controller.indexIntegrity().get("show_banner"));
  }
}
