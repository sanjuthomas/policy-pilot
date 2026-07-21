package com.sanjuthomas.policypilot.vector;

import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import com.sanjuthomas.policypilot.auth.RetrievalScope;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.prompts.AnswerPrompts;
import com.sanjuthomas.policypilot.vector.VectorSearchService.VectorHit;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * Vector-only investigate lane (Python {@code InvestigateHandler} with {@code strategy=vector}).
 * Records {@code path=full_rag}, {@code cypher_provenance=none}, {@code synthesis=gemini_full}.
 */
@Service
public class FullRagLaneService {

  private static final Logger log = LoggerFactory.getLogger(FullRagLaneService.class);

  private final EmbeddingModel embeddingModel;
  private final VectorSearchService vectorSearchService;
  private final ChatClient chatClient;
  private final int retrievalLimit;

  public FullRagLaneService(
      EmbeddingModel embeddingModel,
      VectorSearchService vectorSearchService,
      ChatClient.Builder chatClientBuilder,
      ChatJProperties properties) {
    this.embeddingModel = embeddingModel;
    this.vectorSearchService = vectorSearchService;
    this.chatClient = chatClientBuilder.build();
    this.retrievalLimit = Math.max(1, properties.retrievalLimit());
  }

  public LaneAnswer answer(String message, String mode, Subject subject) {
    String effectiveMode = mode == null || mode.isBlank() ? "events" : mode.strip().toLowerCase(Locale.ROOT);
    Set<String> allowedLobs = RetrievalScope.allowedRetrievalLobs(subject);
    String searchSource = searchSourceForMode(effectiveMode);
    List<VectorHit> hits;
    try {
      float[] embedding = embeddingModel.embed(message == null ? "" : message);
      hits = vectorSearchService.search(embedding, retrievalLimit, searchSource, allowedLobs);
    } catch (RuntimeException ex) {
      log.warn("vector search failed: {}", ex.toString());
      hits = List.of();
    }
    String context = buildContext(hits, effectiveMode);
    String answer;
    try {
      String content =
          chatClient
              .prompt()
              .system(AnswerPrompts.forMode(effectiveMode))
              .user("Context:\n\n" + context + "\n\nQuestion: " + (message == null ? "" : message))
              .call()
              .content();
      answer =
          StringUtils.hasText(content)
              ? content.strip()
              : "I could not synthesize an answer from the retrieved context.";
    } catch (RuntimeException ex) {
      log.warn("Gemini synthesis failed: {}", ex.toString());
      answer = "I could not synthesize an answer from the retrieved context.";
    }
    return LaneAnswer.fullRag(answer, toSources(hits));
  }

  static String searchSourceForMode(String mode) {
    return switch (mode) {
      case "events" -> "security_events";
      case "instructions" -> "instruction_state";
      case "payments" -> "payment";
      default -> null;
    };
  }

  static String buildContext(List<VectorHit> hits, String mode) {
    List<String> sections = new ArrayList<>();
    if ("events".equals(mode)) {
      sections.add(
          "Search mode: SECURITY EVENTS (instruction + payment security event log)");
    } else if ("instructions".equals(mode)) {
      sections.add(
          "Search mode: INSTRUCTIONS (instruction master graph — independent of security events)");
    } else if ("payments".equals(mode)) {
      sections.add("Search mode: PAYMENTS (payment records only)");
    }
    if (hits == null || hits.isEmpty()) {
      sections.add("No indexed data was found.");
      return String.join("\n\n", sections);
    }
    List<String> lines = new ArrayList<>();
    int index = 1;
    for (VectorHit hit : hits) {
      lines.add(formatHit(index++, hit));
    }
    sections.add("Retrieved vector results:\n" + String.join("\n", lines));
    return String.join("\n\n", sections);
  }

  private static String formatHit(int index, VectorHit hit) {
    Map<String, Object> merged = hit.merged() == null ? Map.of() : hit.merged();
    String payloadSource = stringVal(hit.payload() == null ? null : hit.payload().get("source"));
    if (!StringUtils.hasText(payloadSource)) {
      payloadSource = stringVal(merged.get("source"));
    }
    String why =
        firstNonBlank(
            stringVal(merged.get("authorization_summary")),
            stringVal(merged.get("reason")),
            stringVal(merged.get("message")),
            VectorSearchService.summaryFromHit(hit));
    if ("payment_security_event".equals(payloadSource)) {
      return String.format(
          Locale.ROOT,
          "[%d] PAYMENT SECURITY EVENT event_id=%s payment_id=%s instruction_id=%s score=%.4f%n"
              + "  time=%s action=%s severity=%s outcome=%s actor=%s%n"
              + "  lob=%s%n"
              + "  why=%s",
          index,
          nullToEmpty(hit.eventId()),
          nullToEmpty(hit.paymentId()),
          nullToEmpty(hit.instructionId()),
          hit.score(),
          nullToEmpty(stringVal(merged.get("timestamp"))),
          nullToEmpty(stringVal(merged.get("action"))),
          nullToEmpty(stringVal(merged.get("severity"))),
          nullToEmpty(stringVal(merged.get("outcome"))),
          nullToEmpty(stringVal(merged.get("actor_display"))),
          nullToEmpty(firstNonBlank(hit.owningLob(), stringVal(merged.get("owning_lob")))),
          nullToEmpty(why));
    }
    return String.format(
        Locale.ROOT,
        "[%d] INSTRUCTION SECURITY EVENT event_id=%s instruction_id=%s sources=[vector] score=%.4f%n"
            + "  time=%s action=%s severity=%s outcome=%s actor=%s lob=%s%n"
            + "  why=%s",
        index,
        nullToEmpty(hit.eventId()),
        nullToEmpty(hit.instructionId()),
        hit.score(),
        nullToEmpty(stringVal(merged.get("timestamp"))),
        nullToEmpty(stringVal(merged.get("action"))),
        nullToEmpty(stringVal(merged.get("severity"))),
        nullToEmpty(stringVal(merged.get("outcome"))),
        nullToEmpty(
            firstNonBlank(
                stringVal(merged.get("actor_display")), stringVal(merged.get("actor_user_id")))),
        nullToEmpty(firstNonBlank(hit.owningLob(), stringVal(merged.get("owning_lob")))),
        nullToEmpty(why));
  }

  static List<SourceHit> toSources(List<VectorHit> hits) {
    if (hits == null || hits.isEmpty()) {
      return List.of();
    }
    List<SourceHit> sources = new ArrayList<>(hits.size());
    for (VectorHit hit : hits) {
      sources.add(
          new SourceHit(
              hit.eventId(),
              hit.instructionId(),
              Math.round(hit.score() * 10000.0) / 10000.0,
              List.of("vector"),
              VectorSearchService.summaryFromHit(hit),
              hit.merged(),
              hit.securityEvent()));
    }
    return sources;
  }

  private static String stringVal(Object value) {
    return value == null ? null : String.valueOf(value);
  }

  private static String firstNonBlank(String... values) {
    if (values == null) {
      return null;
    }
    for (String value : values) {
      if (StringUtils.hasText(value)) {
        return value.strip();
      }
    }
    return null;
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
