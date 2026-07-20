package com.policypilot.chatj.api;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class ApiModels {

  private ApiModels() {}

  public record LoginRequest(String user_id, String password) {}

  public record LoginResponse(
      String user_id,
      String session_id,
      String session_token,
      List<String> roles,
      List<String> audiences) {}

  public record ChatMessage(String role, String content) {}

  public record ChatRequest(String message, List<ChatMessage> history, String mode) {
    public ChatRequest {
      if (history == null) {
        history = List.of();
      }
      if (mode == null || mode.isBlank()) {
        mode = "events";
      }
    }
  }

  public record ChatFeedbackRequest(
      String rating,
      String mode,
      String path,
      String cypher_provenance,
      String answer_synthesis,
      String retrieval_strategy,
      String intent_id,
      String question_hash) {}

  @JsonInclude(JsonInclude.Include.NON_NULL)
  public record AnswerRoutingInfo(
      String path,
      String cypher_provenance,
      String answer_synthesis,
      String label,
      String intent_id,
      String retrieval_strategy,
      String requested_path) {}

  @JsonInclude(JsonInclude.Include.NON_NULL)
  public record SourceHit(
      String event_id,
      String instruction_id,
      double score,
      List<String> sources,
      String summary,
      Map<String, Object> merged,
      Map<String, Object> security_event) {}

  @JsonInclude(JsonInclude.Include.NON_NULL)
  public record ChatResponse(
      String answer,
      List<SourceHit> sources,
      String cypher,
      List<Map<String, Object>> graph_rows,
      Double retrieval_ms,
      Double generation_ms,
      AnswerRoutingInfo routing,
      List<String> skill_activities,
      Map<String, Object> skill_confirmation,
      Integer retry_after_seconds) {

    public static ChatResponse of(String answer, AnswerRoutingInfo routing) {
      return new ChatResponse(
          answer,
          List.of(),
          null,
          new ArrayList<>(),
          null,
          null,
          routing,
          List.of(),
          null,
          null);
    }
  }
}
