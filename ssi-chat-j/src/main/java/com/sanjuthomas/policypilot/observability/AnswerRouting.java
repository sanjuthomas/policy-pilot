package com.sanjuthomas.policypilot.observability;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Routing snapshot for a finalized chat answer — mirrors Python {@code AnswerRouting} /
 * attribute keys used by OpenSLO chat SLIs.
 */
public record AnswerRouting(
    String path,
    String cypherProvenance,
    String answerSynthesis,
    String mode,
    String retrievalStrategy,
    String intentId,
    Double retrievalMs,
    Double generationMs,
    int sourceCount,
    int graphRowCount,
    Map<String, Integer> sourceChannels,
    int questionLength,
    String questionHash,
    String requestedPath) {

  public AnswerRouting {
    if (sourceChannels == null) {
      sourceChannels = Map.of();
    } else {
      sourceChannels = Map.copyOf(sourceChannels);
    }
  }

  public String cypherClass() {
    return ChatObservability.cypherClassForProvenance(cypherProvenance);
  }

  public boolean routeOverridden() {
    return requestedPath != null && !requestedPath.isBlank() && !requestedPath.equals(path);
  }

  public Map<String, String> pathDecisionLabels() {
    String requested = (requestedPath == null || requestedPath.isBlank()) ? path : requestedPath;
    return Map.of(
        "chat.requested_path", requested,
        "chat.executed_path", path,
        "chat.route_override", routeOverridden() ? "true" : "false",
        "chat.mode", mode == null ? "" : mode);
  }

  public Map<String, Object> logFields() {
    Map<String, Object> fields = new LinkedHashMap<>();
    fields.put("chat.event", "chat.answer.completed");
    fields.put("chat.retrieval_strategy", retrievalStrategy);
    fields.put("chat.path", path);
    fields.put("chat.cypher_provenance", cypherProvenance);
    fields.put("chat.cypher_class", cypherClass());
    fields.put("chat.answer_synthesis", answerSynthesis);
    fields.put("chat.intent_id", intentId);
    fields.put("chat.mode", mode);
    fields.put("chat.retrieval_ms", retrievalMs);
    fields.put("chat.generation_ms", generationMs);
    fields.put("chat.source_count", sourceCount);
    fields.put("chat.graph_row_count", graphRowCount);
    fields.put("chat.question_length", questionLength);
    fields.put("chat.question_hash", questionHash);
    fields.put("chat.route_override", routeOverridden() ? "true" : "false");
    if (routeOverridden()) {
      fields.put("chat.requested_path", requestedPath);
      fields.put("chat.executed_path", path);
    }
    sourceChannels.forEach(
        (channel, count) -> {
          if (count != null && count > 0) {
            fields.put("chat.source_" + channel, count);
          }
        });
    return fields;
  }

  public static QuestionFingerprint fingerprint(String message) {
    String normalized = message == null ? "" : message.strip();
    return new QuestionFingerprint(normalized.length(), sha256Prefix(normalized));
  }

  private static String sha256Prefix(String value) {
    try {
      MessageDigest digest = MessageDigest.getInstance("SHA-256");
      byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
      StringBuilder sb = new StringBuilder(16);
      for (int i = 0; i < 8; i++) {
        sb.append(String.format("%02x", hash[i]));
      }
      return sb.toString();
    } catch (NoSuchAlgorithmException ex) {
      throw new IllegalStateException("SHA-256 unavailable", ex);
    }
  }

  public record QuestionFingerprint(int length, String hash) {}
}
