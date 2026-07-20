package com.sanjuthomas.policypilot.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.api.ApiModels.AnswerRoutingInfo;
import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.api.ApiModels.LoginRequest;
import com.sanjuthomas.policypilot.api.ApiModels.LoginResponse;
import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ApiModelsTest {

  @Test
  void chatRequestDefaultsHistoryAndMode() {
    ChatRequest request = new ChatRequest("hello", null, "  ");
    assertEquals(List.of(), request.history());
    assertEquals("events", request.mode());
  }

  @Test
  void chatResponseFactoryBuildsMinimalPayload() {
    AnswerRoutingInfo routing =
        new AnswerRoutingInfo("eligibility", "none", "eligibility_api", "label", null, "eligibility", null);
    ChatResponse response = ChatResponse.of("answer text", routing);

    assertEquals("answer text", response.answer());
    assertEquals(routing, response.routing());
    assertTrue(response.sources().isEmpty());
    assertNotNull(response.graph_rows());
  }

  @Test
  void recordsExposeFields() {
    LoginRequest login = new LoginRequest("alice", "secret");
    LoginResponse loginResponse =
        new LoginResponse("alice", "sess", "tok", List.of("R"), List.of("aud"));
    SourceHit hit =
        new SourceHit("e1", "i1", 0.9, List.of("src"), "summary", Map.of(), Map.of("k", "v"));

    assertEquals("alice", login.user_id());
    assertEquals("sess", loginResponse.session_id());
    assertEquals("e1", hit.event_id());
  }
}
