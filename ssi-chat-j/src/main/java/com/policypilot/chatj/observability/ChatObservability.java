package com.policypilot.chatj.observability;

import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Shared classifiers / labels aligned with Python {@code chat_application.observability}. */
public final class ChatObservability {

  public static final Set<String> SOURCE_CHANNELS = Set.of("vector", "neo4j", "exact");

  public static final Set<String> RETRIEVAL_STRATEGIES =
      Set.of("deterministic", "graph", "vector", "eligibility", "policy_directory", "skill");

  private ChatObservability() {}

  public static String cypherClassForProvenance(String provenance) {
    if ("predefined_yaml".equals(provenance) || "predefined_planned".equals(provenance)) {
      return "deterministic";
    }
    if ("llm_graph_plan".equals(provenance)) {
      return "llm";
    }
    return "none";
  }

  public static String classifyRetrievalStrategy(
      String path,
      String cypherProvenance,
      String answerSynthesis,
      Map<String, Integer> sourceChannels,
      int graphRowCount) {
    if ("eligibility".equals(path)) {
      return "eligibility";
    }
    if ("policy_directory".equals(path)) {
      return "policy_directory";
    }
    if ("policy_summary".equals(path) || "person_permissions".equals(path)) {
      return "eligibility";
    }
    if ("skill".equals(path)) {
      return "skill";
    }
    if ("me".equals(path) || "neo4j_direct".equals(path)) {
      return "deterministic";
    }

    Map<String, Integer> channels = sourceChannels == null ? Map.of() : sourceChannels;
    int vectorHits = channels.getOrDefault("vector", 0);
    int graphHits = channels.getOrDefault("neo4j", 0) + channels.getOrDefault("exact", 0);

    if ("gemini_full".equals(answerSynthesis)
        && vectorHits > 0
        && vectorHits >= graphHits
        && graphRowCount == 0) {
      return "vector";
    }
    if ("predefined_planned".equals(cypherProvenance)
        || "llm_graph_plan".equals(cypherProvenance)
        || graphRowCount > 0
        || "formatter".equals(answerSynthesis)
        || "gemini_why_only".equals(answerSynthesis)) {
      return "graph";
    }
    if (vectorHits > graphHits) {
      return "vector";
    }
    return "graph";
  }

  public static String normalizeStrategy(String strategy) {
    if (strategy != null && RETRIEVAL_STRATEGIES.contains(strategy)) {
      return strategy;
    }
    return null;
  }

  public static String pathPairKey(String requested, String executed) {
    return requested + "->" + executed;
  }

  public static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }

  public static String lower(String value) {
    return value == null ? "" : value.toLowerCase(Locale.ROOT);
  }
}
