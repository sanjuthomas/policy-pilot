package com.sanjuthomas.policypilot.observability;

import com.sanjuthomas.policypilot.api.ApiModels.AnswerRoutingInfo;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import com.sanjuthomas.policypilot.gemini.GeminiErrors;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * Builds the API response and records routing / skill metrics — parity with Python {@code
 * finalize_chat_response}.
 */
@Component
public class ChatAnswerFinalizer {

  private final RoutingMetrics routingMetrics;
  private final SkillMetrics skillMetrics;

  public ChatAnswerFinalizer(RoutingMetrics routingMetrics, SkillMetrics skillMetrics) {
    this.routingMetrics = routingMetrics;
    this.skillMetrics = skillMetrics;
  }

  public ChatResponse finalizeAnswer(
      String message,
      String mode,
      String answer,
      List<SourceHit> sources,
      String cypher,
      List<Map<String, Object>> graphRows,
      Double retrievalMs,
      Double generationMs,
      String path,
      String cypherProvenance,
      String answerSynthesis,
      String intentId,
      List<String> skillActivities,
      Map<String, Object> skillConfirmation,
      Integer retryAfterSeconds,
      String requestedPath) {

    AnswerRouting.QuestionFingerprint fingerprint = AnswerRouting.fingerprint(message);
    Map<String, Integer> sourceChannels = countSourceChannels(sources);
    int graphRowCount = graphRows == null ? 0 : graphRows.size();
    String retrievalStrategy =
        ChatObservability.classifyRetrievalStrategy(
            path, cypherProvenance, answerSynthesis, sourceChannels, graphRowCount);

    String effectiveRequested = requestedPath;
    if (effectiveRequested != null && effectiveRequested.equals(path)) {
      effectiveRequested = null;
    }

    Double retrievalRounded = retrievalMs == null ? null : round1(retrievalMs);
    Double generationRounded = generationMs == null ? null : round1(generationMs);

    AnswerRouting routing =
        new AnswerRouting(
            path,
            cypherProvenance,
            answerSynthesis,
            mode == null || mode.isBlank() ? "events" : mode,
            retrievalStrategy,
            intentId,
            retrievalRounded,
            generationRounded,
            sources == null ? 0 : sources.size(),
            graphRowCount,
            sourceChannels,
            fingerprint.length(),
            fingerprint.hash(),
            effectiveRequested);

    routingMetrics.record(routing);
    if ("skill".equals(path)) {
      skillMetrics.recordSkillOutcome(intentId);
    }

    List<Map<String, Object>> trimmedRows = new ArrayList<>();
    if (graphRows != null) {
      int limit = Math.min(20, graphRows.size());
      for (int i = 0; i < limit; i++) {
        trimmedRows.add(graphRows.get(i));
      }
    }

    return new ChatResponse(
        answer,
        sources == null ? List.of() : sources,
        cypher,
        trimmedRows,
        retrievalRounded,
        generationRounded,
        toApi(routing),
        skillActivities == null ? List.of() : skillActivities,
        skillConfirmation,
        retryAfterSeconds);
  }

  /**
   * Soft HTTP 200 rate-limit UX (Gemini 429). Client shows the Vendor-under-stress countdown then
   * Retry — parity with Python {@code _rate_limited_response}.
   */
  public ChatResponse rateLimited(
      String message, String mode, String path, Double retrievalMs) {
    return finalizeAnswer(
        message,
        mode,
        GeminiErrors.RATE_LIMIT_ANSWER,
        List.of(),
        null,
        List.of(),
        retrievalMs,
        0.0,
        path == null || path.isBlank() ? "full_rag" : path,
        "none",
        "formatter",
        GeminiErrors.RATE_LIMIT_INTENT_ID,
        List.of(),
        null,
        GeminiErrors.RATE_LIMIT_RETRY_SECONDS,
        null);
  }

  public ChatResponse of(
      String message,
      String mode,
      String answer,
      String path,
      String answerSynthesis,
      String requestedPath,
      Double retrievalMs,
      Double generationMs) {
    return of(
        message,
        mode,
        answer,
        path,
        answerSynthesis,
        requestedPath,
        retrievalMs,
        generationMs,
        null);
  }

  public ChatResponse of(
      String message,
      String mode,
      String answer,
      String path,
      String answerSynthesis,
      String requestedPath,
      Double retrievalMs,
      Double generationMs,
      String intentId) {
    return of(
        message,
        mode,
        answer,
        path,
        answerSynthesis,
        requestedPath,
        retrievalMs,
        generationMs,
        intentId,
        null,
        List.of(),
        "none");
  }

  public ChatResponse of(
      String message,
      String mode,
      String answer,
      String path,
      String answerSynthesis,
      String requestedPath,
      Double retrievalMs,
      Double generationMs,
      String intentId,
      String cypher,
      List<Map<String, Object>> graphRows,
      String cypherProvenance) {
    return of(
        message,
        mode,
        answer,
        path,
        answerSynthesis,
        requestedPath,
        retrievalMs,
        generationMs,
        intentId,
        cypher,
        graphRows,
        cypherProvenance,
        List.of());
  }

  public ChatResponse of(
      String message,
      String mode,
      String answer,
      String path,
      String answerSynthesis,
      String requestedPath,
      Double retrievalMs,
      Double generationMs,
      String intentId,
      String cypher,
      List<Map<String, Object>> graphRows,
      String cypherProvenance,
      List<SourceHit> sources) {
    return of(
        message,
        mode,
        answer,
        path,
        answerSynthesis,
        requestedPath,
        retrievalMs,
        generationMs,
        intentId,
        cypher,
        graphRows,
        cypherProvenance,
        sources,
        List.of(),
        null);
  }

  public ChatResponse of(
      String message,
      String mode,
      String answer,
      String path,
      String answerSynthesis,
      String requestedPath,
      Double retrievalMs,
      Double generationMs,
      String intentId,
      String cypher,
      List<Map<String, Object>> graphRows,
      String cypherProvenance,
      List<SourceHit> sources,
      List<String> skillActivities,
      Map<String, Object> skillConfirmation) {
    return finalizeAnswer(
        message,
        mode,
        answer,
        sources == null ? List.of() : sources,
        cypher,
        graphRows == null ? List.of() : graphRows,
        retrievalMs,
        generationMs,
        path,
        cypherProvenance == null ? "none" : cypherProvenance,
        answerSynthesis,
        intentId,
        skillActivities == null ? List.of() : skillActivities,
        skillConfirmation,
        null,
        requestedPath);
  }

  private static AnswerRoutingInfo toApi(AnswerRouting routing) {
    return new AnswerRoutingInfo(
        routing.path(),
        routing.cypherProvenance(),
        routing.answerSynthesis(),
        formatLabel(routing),
        routing.intentId(),
        routing.retrievalStrategy(),
        routing.requestedPath());
  }

  private static String formatLabel(AnswerRouting routing) {
    if (GeminiErrors.RATE_LIMIT_INTENT_ID.equals(routing.intentId())) {
      return "Gemini rate limited";
    }
    String pathLabel =
        switch (routing.path()) {
          case "eligibility" -> "Eligibility shortcut";
          case "document_extraction" -> "Document extraction (API)";
          case "instruction_show" -> "Document extraction (API)";
          case "policy_directory" -> "Policy directory";
          case "policy_summary" -> "Policy summary";
          case "person_permissions" -> "Person permissions";
          case "neo4j_direct" -> "Neo4j direct (early exit)";
          case "full_rag" -> "Full RAG (vector + graph)";
          case "skill" -> "Mutation skill";
          case "me" -> "Me / identity";
          default -> "ssi-chat-j (" + routing.path() + ")";
        };
    String cypherLabel =
        switch (routing.cypherProvenance()) {
          case "predefined_yaml" -> "Predefined Cypher (YAML)";
          case "predefined_planned" -> "Predefined Cypher (planned)";
          case "llm_graph_plan" -> "LLM-generated Cypher";
          default -> "No Cypher";
        };
    String synthesisLabel =
        switch (routing.answerSynthesis()) {
          case "formatter" -> "Deterministic formatter";
          case "gemini_full" -> "Gemini (full answer)";
          case "gemini_why_only" -> "Gemini (WHY rewrite only)";
          case "eligibility_api" -> "Eligibility API (OPA)";
          case "policy_directory_api" -> "Policy directory API";
          default -> routing.answerSynthesis();
        };
    String base = pathLabel + " · " + cypherLabel + " · " + synthesisLabel;
    if (routing.intentId() != null && !routing.intentId().isBlank()) {
      return base + " · intent=" + routing.intentId();
    }
    return base;
  }

  static Map<String, Integer> countSourceChannels(List<SourceHit> sources) {
    Map<String, Integer> counts = new HashMap<>();
    for (String channel : ChatObservability.SOURCE_CHANNELS) {
      counts.put(channel, 0);
    }
    if (sources == null) {
      return counts;
    }
    for (SourceHit source : sources) {
      if (source == null || source.sources() == null) {
        continue;
      }
      for (String channel : source.sources()) {
        if (ChatObservability.SOURCE_CHANNELS.contains(channel)) {
          counts.merge(channel, 1, Integer::sum);
        }
      }
    }
    return counts;
  }

  private static double round1(double value) {
    return Math.round(value * 10.0) / 10.0;
  }
}
