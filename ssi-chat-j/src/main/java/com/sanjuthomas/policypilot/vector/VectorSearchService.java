package com.sanjuthomas.policypilot.vector;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import com.sanjuthomas.policypilot.neo4j.Neo4jQueryExecutor;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * Neo4j dense vector read path over {@code MultimodalDocument} nodes (parity with Python {@code
 * VectorSearchClient}).
 */
@Service
public class VectorSearchService {

  private static final ObjectMapper MAPPER = new ObjectMapper();
  private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};

  private final Neo4jQueryExecutor neo4jQueryExecutor;
  private final String vectorIndex;
  private final int defaultLimit;

  public VectorSearchService(Neo4jQueryExecutor neo4jQueryExecutor, ChatJProperties properties) {
    this.neo4jQueryExecutor = neo4jQueryExecutor;
    this.vectorIndex = sanitizeIndex(properties.multimodalVectorIndex());
    this.defaultLimit = Math.max(1, properties.retrievalLimit());
  }

  public List<VectorHit> search(
      float[] embedding,
      int limit,
      String sourceFilter,
      Set<String> allowedLobs) {
    if (allowedLobs != null && allowedLobs.isEmpty()) {
      return List.of();
    }
    if (embedding == null || embedding.length == 0) {
      return List.of();
    }
    int effectiveLimit = limit > 0 ? limit : defaultLimit;
    List<String> sources = sourceFilterValues(sourceFilter);
    List<String> allowedList =
        allowedLobs == null ? null : allowedLobs.stream().sorted().toList();
    List<Double> vector = new ArrayList<>(embedding.length);
    for (float value : embedding) {
      vector.add((double) value);
    }
    // Index name must be inlined (parity with Python); sanitized to [A-Za-z0-9_]+.
    String cypher =
        """
        CALL db.index.vector.queryNodes('%s', $limit, $embedding)
        YIELD node, score
        WHERE ($sources IS NULL OR node.source IN $sources)
          AND ($allowed_lobs IS NULL OR node.owning_lob IN $allowed_lobs)
        RETURN node, score
        ORDER BY score DESC
        LIMIT $limit
        """
            .formatted(vectorIndex);
    Map<String, Object> params = new LinkedHashMap<>();
    params.put("limit", effectiveLimit);
    params.put("embedding", vector);
    params.put("sources", sources);
    params.put("allowed_lobs", allowedList);
    List<Map<String, Object>> rows = neo4jQueryExecutor.runRead(cypher, params);
    List<VectorHit> hits = new ArrayList<>();
    for (Map<String, Object> row : rows) {
      Object nodeObj = row.get("node");
      if (!(nodeObj instanceof Map<?, ?> rawNode)) {
        continue;
      }
      @SuppressWarnings("unchecked")
      Map<String, Object> node = (Map<String, Object>) rawNode;
      double score = toDouble(row.get("score"));
      hits.add(toHit(node, score));
    }
    return hits;
  }

  static VectorHit toHit(Map<String, Object> node, double score) {
    Map<String, Object> payload = payloadFromNode(node);
    Map<String, Object> merged = asMap(payload.get("merged"));
    String payloadSource = stringOrNull(payload.get("source"));
    if (merged.isEmpty()
        && payloadSource != null
        && Set.of("payment_security_event", "payment_fact", "instruction_state")
            .contains(payloadSource)) {
      merged = payload;
    }
    Map<String, Object> securityEvent = asMap(payload.get("security_event"));
    String owningLob = stringOrNull(node.get("owning_lob"));
    if (owningLob == null) {
      owningLob = stringOrNull(payload.get("owning_lob"));
    }
    if (owningLob != null) {
      owningLob = owningLob.strip().toUpperCase(Locale.ROOT);
      if (owningLob.isEmpty()) {
        owningLob = null;
      }
    }
    String eventId = stringOrNull(payload.get("event_id"));
    if (eventId == null) {
      eventId = stringOrNull(node.get("event_id"));
    }
    String instructionId = stringOrNull(payload.get("instruction_id"));
    if (instructionId == null) {
      instructionId = stringOrNull(node.get("instruction_id"));
    }
    String paymentId = stringOrNull(payload.get("payment_id"));
    if (paymentId == null) {
      paymentId = stringOrNull(node.get("payment_id"));
    }
    String searchText = stringOrNull(node.get("search_text"));
    if (searchText == null) {
      searchText = stringOrNull(payload.get("search_text"));
    }
    if (searchText == null) {
      searchText = "";
    }
    return new VectorHit(
        "vector",
        score,
        eventId,
        instructionId,
        paymentId,
        owningLob,
        searchText,
        merged,
        securityEvent,
        payload);
  }

  static String summaryFromHit(VectorHit hit) {
    Map<String, Object> merged = hit.merged() == null ? Map.of() : hit.merged();
    Object auth = merged.get("authorization_summary");
    if (auth != null && StringUtils.hasText(String.valueOf(auth))) {
      return String.valueOf(auth);
    }
    List<String> parts = new ArrayList<>();
    for (String key :
        List.of(
            "action",
            "severity",
            "actor_user_id",
            "creator_user_id",
            "event_reason",
            "reason",
            "message")) {
      Object value = merged.get(key);
      if (value != null && StringUtils.hasText(String.valueOf(value))) {
        parts.add(String.valueOf(value));
      }
    }
    if (parts.isEmpty() && StringUtils.hasText(hit.searchText())) {
      String text = hit.searchText();
      parts.add(text.length() > 200 ? text.substring(0, 200) : text);
    }
    return String.join(" · ", parts);
  }

  private static List<String> sourceFilterValues(String source) {
    if (source == null || source.isBlank()) {
      return null;
    }
    if ("security_events".equals(source)) {
      return List.of("instruction_security_event", "payment_security_event");
    }
    if ("payment".equals(source)) {
      return List.of("payment_fact");
    }
    return List.of(source);
  }

  private static Map<String, Object> payloadFromNode(Map<String, Object> node) {
    Object raw = node.get("payload_json");
    if (raw == null) {
      return Map.of();
    }
    if (raw instanceof Map<?, ?> map) {
      @SuppressWarnings("unchecked")
      Map<String, Object> typed = (Map<String, Object>) map;
      return typed;
    }
    if (raw instanceof String text && StringUtils.hasText(text)) {
      try {
        return MAPPER.readValue(text, MAP_TYPE);
      } catch (Exception ignored) {
        return Map.of();
      }
    }
    return Map.of();
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> asMap(Object value) {
    if (value instanceof Map<?, ?> map) {
      return (Map<String, Object>) map;
    }
    return Map.of();
  }

  private static String stringOrNull(Object value) {
    if (value == null) {
      return null;
    }
    String text = String.valueOf(value).strip();
    return text.isEmpty() ? null : text;
  }

  private static double toDouble(Object value) {
    if (value instanceof Number number) {
      return number.doubleValue();
    }
    return 0.0;
  }

  private static String sanitizeIndex(String index) {
    String value = StringUtils.hasText(index) ? index.strip() : "multimodal_embedding";
    if (!value.matches("[A-Za-z0-9_]+")) {
      throw new IllegalArgumentException("Invalid multimodal vector index name: " + value);
    }
    return value;
  }

  /** One dense-retrieval hit. */
  public record VectorHit(
      String source,
      double score,
      String eventId,
      String instructionId,
      String paymentId,
      String owningLob,
      String searchText,
      Map<String, Object> merged,
      Map<String, Object> securityEvent,
      Map<String, Object> payload) {}
}
