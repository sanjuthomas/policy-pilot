package com.sanjuthomas.policypilot.pipeline;

import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import java.util.List;
import java.util.Map;

/**
 * Uniform lane result for ChatService finalize (path services stay free of observability).
 */
public record LaneAnswer(
    String answer,
    String recordedPath,
    String synthesis,
    String intentId,
    String cypher,
    List<Map<String, Object>> graphRows,
    String cypherProvenance,
    List<SourceHit> sources) {

  public static LaneAnswer of(String answer, String recordedPath, String synthesis) {
    return of(answer, recordedPath, synthesis, null);
  }

  public static LaneAnswer of(
      String answer, String recordedPath, String synthesis, String intentId) {
    return new LaneAnswer(
        answer, recordedPath, synthesis, intentId, null, List.of(), "none", List.of());
  }

  public static LaneAnswer neo4j(
      String answer,
      String intentId,
      String cypher,
      List<Map<String, Object>> graphRows,
      String cypherProvenance) {
    return new LaneAnswer(
        answer,
        "neo4j_direct",
        "formatter",
        intentId,
        cypher,
        graphRows == null ? List.of() : graphRows,
        cypherProvenance == null ? "none" : cypherProvenance,
        List.of());
  }

  public static LaneAnswer fullRag(String answer, List<SourceHit> sources) {
    return new LaneAnswer(
        answer,
        "full_rag",
        "gemini_full",
        null,
        null,
        List.of(),
        "none",
        sources == null ? List.of() : sources);
  }
}
