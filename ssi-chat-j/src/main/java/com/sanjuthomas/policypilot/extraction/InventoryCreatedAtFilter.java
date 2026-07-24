package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.time.GraphTimeWindow;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.util.StringUtils;

/**
 * Client-side {@code created_at} window filter for domain-API inventory rows when list endpoints
 * lack a created-at query param. Windows match {@link GraphTimeWindow} /
 * {@code RouterDecision.graphTimeWindow}.
 */
final class InventoryCreatedAtFilter {

  private InventoryCreatedAtFilter() {}

  static List<Map<String, Object>> apply(List<Map<String, Object>> rows, String timeWindow) {
    if (rows == null || rows.isEmpty() || !StringUtils.hasText(timeWindow)) {
      return rows == null ? List.of() : rows;
    }
    Instant start = GraphTimeWindow.startInstant(timeWindow);
    if (start == null) {
      return rows;
    }
    List<Map<String, Object>> out = new ArrayList<>();
    for (Map<String, Object> row : rows) {
      if (row == null) {
        continue;
      }
      Instant created = parseInstant(row.get("created_at"));
      // Missing/unparseable timestamps: keep the row so soft counts still work when list
      // payloads omit created_at; strict empty only when timestamps are present and outside window.
      if (created == null || !created.isBefore(start)) {
        out.add(row);
      }
    }
    return out;
  }

  static Instant parseInstant(Object raw) {
    if (raw == null) {
      return null;
    }
    if (raw instanceof Instant instant) {
      return instant;
    }
    String text = raw.toString().strip();
    if (text.isEmpty()) {
      return null;
    }
    try {
      return Instant.parse(text);
    } catch (DateTimeParseException ignored) {
      // fall through
    }
    try {
      if (text.endsWith("Z")) {
        return Instant.parse(text);
      }
      return Instant.parse(text + "Z");
    } catch (DateTimeParseException ignored) {
      return null;
    }
  }
}
