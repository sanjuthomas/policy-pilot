package com.sanjuthomas.policypilot.neo4j;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Locale;
import org.springframework.util.StringUtils;

/**
 * Display slots for neo4j_direct alert/count/list/ranking answers — filled by the router, not by
 * free-text paraphrase scraping in the formatter.
 */
public record GraphAnswerHints(String timeWindow, String eventScope, String eventKind) {

  public static GraphAnswerHints from(RouterDecision decision) {
    if (decision == null) {
      return empty();
    }
    return new GraphAnswerHints(
        normalizeWindow(decision.getGraphTimeWindow()),
        normalizeScope(decision.getGraphEventScope()),
        normalizeKind(decision.getGraphEventKind()));
  }

  public static GraphAnswerHints empty() {
    return new GraphAnswerHints(null, null, null);
  }

  public String scopePrefix() {
    if ("payment".equals(eventScope)) {
      return "payment ";
    }
    if ("instruction".equals(eventScope)) {
      return "instruction ";
    }
    return "";
  }

  public String eventLabel() {
    if ("denial".equals(eventKind) || "approval_denial".equals(eventKind)) {
      return "policy denial";
    }
    return "ALERT";
  }

  public String periodSuffix() {
    if ("today".equals(timeWindow)) {
      return " today";
    }
    if ("week".equals(timeWindow)) {
      return " this week";
    }
    return "";
  }

  public String periodWord() {
    if ("today".equals(timeWindow)) {
      return "today";
    }
    if ("week".equals(timeWindow)) {
      return "this week";
    }
    return "all time";
  }

  public String rankingDomain() {
    if ("payment".equals(eventScope)) {
      return "payment policy denial alerts";
    }
    if ("instruction".equals(eventScope)) {
      return "instruction policy denial alerts";
    }
    return "policy denial alerts";
  }

  public boolean approvalDenialList() {
    return "approval_denial".equals(eventKind);
  }

  private static String normalizeWindow(String raw) {
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    String key = raw.strip().toLowerCase(Locale.ROOT);
    return switch (key) {
      case "today" -> "today";
      case "week", "this_week", "this-week" -> "week";
      case "all", "all_time", "all-time" -> "all";
      default -> null;
    };
  }

  private static String normalizeScope(String raw) {
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    String key = raw.strip().toLowerCase(Locale.ROOT);
    if ("payment".equals(key) || "instruction".equals(key)) {
      return key;
    }
    return null;
  }

  private static String normalizeKind(String raw) {
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    String key = raw.strip().toLowerCase(Locale.ROOT).replace('-', '_');
    return switch (key) {
      case "alert" -> "alert";
      case "denial" -> "denial";
      case "approval_denial" -> "approval_denial";
      default -> null;
    };
  }
}
