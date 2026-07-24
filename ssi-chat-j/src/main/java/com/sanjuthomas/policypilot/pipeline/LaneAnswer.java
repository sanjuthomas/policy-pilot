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
    List<SourceHit> sources,
    List<String> skillActivities,
    Map<String, Object> skillConfirmation) {

  public static LaneAnswer of(String answer, String recordedPath, String synthesis) {
    return of(answer, recordedPath, synthesis, null);
  }

  public static LaneAnswer of(
      String answer, String recordedPath, String synthesis, String intentId) {
    return new LaneAnswer(
        answer, recordedPath, synthesis, intentId, null, List.of(), "none", List.of(), List.of(), null);
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
        List.of(),
        List.of(),
        null);
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
        sources == null ? List.of() : sources,
        List.of(),
        null);
  }

  /** Mutation skill result carrying activity trail + optional confirmation card payload. */
  public static LaneAnswer skill(
      String answer,
      String intentId,
      List<String> activities,
      Map<String, Object> confirmation) {
    return new LaneAnswer(
        answer,
        "skill",
        "formatter",
        intentId,
        null,
        List.of(),
        "none",
        List.of(),
        activities == null ? List.of() : activities,
        confirmation);
  }
}
