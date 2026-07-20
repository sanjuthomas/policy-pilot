package com.policypilot.chatj.observability;

import com.policypilot.chatj.api.ApiModels.AnswerRoutingInfo;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.api.ApiModels.SourceHit;
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

  public ChatResponse of(
      String message,
      String mode,
      String answer,
      String path,
      String answerSynthesis,
      String requestedPath,
      Double retrievalMs,
      Double generationMs) {
    return finalizeAnswer(
        message,
        mode,
        answer,
        List.of(),
        null,
        List.of(),
        retrievalMs,
        generationMs,
        path,
        "none",
        answerSynthesis,
        null,
        List.of(),
        null,
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
    String pathLabel =
        switch (routing.path()) {
          case "eligibility" -> "Eligibility shortcut";
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
