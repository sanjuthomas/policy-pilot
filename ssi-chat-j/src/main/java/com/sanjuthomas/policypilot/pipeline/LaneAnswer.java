package com.sanjuthomas.policypilot.pipeline;

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
    String cypherProvenance) {

  public static LaneAnswer of(String answer, String recordedPath, String synthesis) {
    return of(answer, recordedPath, synthesis, null);
  }

  public static LaneAnswer of(
      String answer, String recordedPath, String synthesis, String intentId) {
    return new LaneAnswer(answer, recordedPath, synthesis, intentId, null, List.of(), "none");
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
        cypherProvenance == null ? "none" : cypherProvenance);
  }
}
