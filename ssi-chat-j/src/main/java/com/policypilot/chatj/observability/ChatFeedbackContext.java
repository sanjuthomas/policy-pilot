package com.policypilot.chatj.observability;

import java.util.LinkedHashMap;
import java.util.Map;

/** Feedback payload context — mirrors Python {@code ChatFeedbackContext}. */
public record ChatFeedbackContext(
    String rating,
    String mode,
    String path,
    String cypherProvenance,
    String answerSynthesis,
    String retrievalStrategy,
    String userId,
    String intentId,
    String questionHash) {

  public static ChatFeedbackContext fromPayload(
      String rating,
      String mode,
      String path,
      String cypherProvenance,
      String answerSynthesis,
      String retrievalStrategy,
      String userId,
      String intentId,
      String questionHash) {
    String strategy = ChatObservability.normalizeStrategy(retrievalStrategy);
    if (strategy == null) {
      strategy =
          ChatObservability.classifyRetrievalStrategy(
              path, cypherProvenance, answerSynthesis, Map.of(), 0);
    }
    return new ChatFeedbackContext(
        rating,
        mode,
        path,
        cypherProvenance,
        answerSynthesis,
        strategy,
        userId,
        intentId,
        questionHash);
  }

  public Map<String, Object> logFields() {
    Map<String, Object> fields = new LinkedHashMap<>();
    fields.put("chat.event", "chat.feedback.received");
    fields.put("chat.feedback_rating", rating);
    fields.put("chat.retrieval_strategy", retrievalStrategy);
    fields.put("chat.path", path);
    fields.put("chat.cypher_provenance", cypherProvenance);
    fields.put(
        "chat.cypher_class", ChatObservability.cypherClassForProvenance(cypherProvenance));
    fields.put("chat.answer_synthesis", answerSynthesis);
    fields.put("chat.mode", mode);
    fields.put("chat.intent_id", intentId);
    fields.put("chat.question_hash", questionHash);
    fields.put("chat.user_id", userId);
    return fields;
  }
}
