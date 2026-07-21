package com.sanjuthomas.policypilot.neo4j;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Deterministic formatters for planned_graph neo4j_direct answers (v1: alert/denial counts).
 * Parity with Python {@code _format_security_event_alert_count_answer}.
 */
@Component
public class Neo4jDirectAnswerFormatter {

  public String format(String question, Set<String> labels, List<Map<String, Object>> rows) {
    if (labels.contains("count") && isAlertCountQuestion(question)) {
      return formatAlertCount(question, rows);
    }
    long total = extractTotal(rows);
    return "Graph query returned " + total + " row(s).";
  }

  static boolean isAlertCountQuestion(String question) {
    String q = question == null ? "" : question.toLowerCase(Locale.ROOT);
    if (!(q.contains("how many") || q.contains("count") || q.contains("number of"))) {
      return false;
    }
    return q.contains("alert")
        || q.contains("denial")
        || q.contains("denied")
        || q.contains("security event");
  }

  private static String formatAlertCount(String question, List<Map<String, Object>> rows) {
    long total = extractTotal(rows);
    String q = question == null ? "" : question.toLowerCase(Locale.ROOT);
    String scope = "";
    if (q.contains("payment")) {
      scope = "payment ";
    } else if (q.contains("instruction")) {
      scope = "instruction ";
    }
    String eventLabel = (q.contains("denial") || q.contains("denied")) ? "policy denial" : "ALERT";
    String suffix;
    if (q.contains("today")) {
      suffix = " today";
    } else if (q.contains("this week") || q.contains("week")) {
      suffix = " this week";
    } else {
      suffix = "";
    }
    if (total == 0) {
      return "There were no " + scope + eventLabel + " events" + suffix + ".";
    }
    if (total == 1) {
      return "There was 1 " + scope + eventLabel + " event" + suffix + ".";
    }
    return "There were " + total + " " + scope + eventLabel + " events" + suffix + ".";
  }

  private static long extractTotal(List<Map<String, Object>> rows) {
    if (rows == null || rows.isEmpty()) {
      return 0L;
    }
    for (Map<String, Object> row : rows) {
      Object total = row.get("total");
      if (total instanceof Number number) {
        return number.longValue();
      }
    }
    return rows.size();
  }
}
