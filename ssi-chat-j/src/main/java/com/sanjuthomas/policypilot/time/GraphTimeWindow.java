package com.sanjuthomas.policypilot.time;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Locale;
import org.springframework.util.StringUtils;

/**
 * Shared {@code RouterDecision.graphTimeWindow} vocabulary for neo4j_direct alerts and
 * document_extraction inventory counts.
 *
 * <p>Canonical values: {@code day}, {@code week}, {@code month}, {@code quarter}, {@code year},
 * {@code all}. {@code today} is accepted as an alias for {@code day}.
 */
public final class GraphTimeWindow {

  public static final String DAY = "day";
  public static final String WEEK = "week";
  public static final String MONTH = "month";
  public static final String QUARTER = "quarter";
  public static final String YEAR = "year";
  public static final String ALL = "all";

  private GraphTimeWindow() {}

  /** Normalize router / paraphrase tokens to a canonical window, or null if unknown/blank. */
  public static String normalize(String raw) {
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    String key = raw.strip().toLowerCase(Locale.ROOT).replace('-', '_');
    return switch (key) {
      case "day", "today" -> DAY;
      case "week", "this_week" -> WEEK;
      case "month", "this_month" -> MONTH;
      case "quarter", "this_quarter" -> QUARTER;
      case "year", "this_year", "ytd" -> YEAR;
      case "all", "all_time" -> ALL;
      default -> null;
    };
  }

  /**
   * Inclusive lower bound for client-side {@code created_at} filters (UTC). Null means no bound
   * ({@code all} / unknown).
   */
  public static Instant startInstant(String window) {
    String key = normalize(window);
    if (key == null || ALL.equals(key)) {
      return null;
    }
    LocalDate today = LocalDate.now(ZoneOffset.UTC);
    return switch (key) {
      case DAY -> today.atStartOfDay().toInstant(ZoneOffset.UTC);
      case WEEK -> Instant.now().minusSeconds(7L * 24 * 60 * 60);
      case MONTH -> today.withDayOfMonth(1).atStartOfDay().toInstant(ZoneOffset.UTC);
      case QUARTER -> firstDayOfQuarter(today).atStartOfDay().toInstant(ZoneOffset.UTC);
      case YEAR -> today.withDayOfYear(1).atStartOfDay().toInstant(ZoneOffset.UTC);
      default -> null;
    };
  }

  /** Neo4j {@code AND …} fragment for SecurityEvent timestamp filtering (may be empty). */
  public static String cypherTimestampFilter(String window) {
    String key = normalize(window);
    if (key == null || ALL.equals(key)) {
      return "";
    }
    return switch (key) {
      case DAY -> "AND date(datetime(e.timestamp)) = date()";
      case WEEK -> "AND date(datetime(e.timestamp)) >= date() - duration('P7D')";
      case MONTH -> "AND date(datetime(e.timestamp)) >= date.truncate('month', date())";
      case QUARTER -> "AND date(datetime(e.timestamp)) >= date.truncate('quarter', date())";
      case YEAR -> "AND date(datetime(e.timestamp)) >= date.truncate('year', date())";
      default -> "";
    };
  }

  /** Leading space + natural phrase for count templates, e.g. {@code " today"}. */
  public static String periodSuffix(String window) {
    String key = normalize(window);
    if (key == null || ALL.equals(key)) {
      return "";
    }
    return switch (key) {
      case DAY -> " today";
      case WEEK -> " this week";
      case MONTH -> " this month";
      case QUARTER -> " this quarter";
      case YEAR -> " this year";
      default -> "";
    };
  }

  /** Bare period word for ranking / list prose. */
  public static String periodWord(String window) {
    String key = normalize(window);
    if (key == null || ALL.equals(key)) {
      return "all time";
    }
    return switch (key) {
      case DAY -> "today";
      case WEEK -> "this week";
      case MONTH -> "this month";
      case QUARTER -> "this quarter";
      case YEAR -> "this year";
      default -> "all time";
    };
  }

  static LocalDate firstDayOfQuarter(LocalDate date) {
    int month = date.getMonthValue();
    int firstMonth = ((month - 1) / 3) * 3 + 1;
    return LocalDate.of(date.getYear(), firstMonth, 1);
  }
}
