package com.sanjuthomas.policypilot.time;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;

class GraphTimeWindowTest {

  @Test
  void normalizesDayWeekMonthQuarterYearAndAliases() {
    assertEquals(GraphTimeWindow.DAY, GraphTimeWindow.normalize("day"));
    assertEquals(GraphTimeWindow.DAY, GraphTimeWindow.normalize("today"));
    assertEquals(GraphTimeWindow.WEEK, GraphTimeWindow.normalize("this_week"));
    assertEquals(GraphTimeWindow.MONTH, GraphTimeWindow.normalize("this-month"));
    assertEquals(GraphTimeWindow.QUARTER, GraphTimeWindow.normalize("quarter"));
    assertEquals(GraphTimeWindow.YEAR, GraphTimeWindow.normalize("ytd"));
    assertEquals(GraphTimeWindow.ALL, GraphTimeWindow.normalize("all_time"));
    assertNull(GraphTimeWindow.normalize("fortnight"));
  }

  @Test
  void startInstantUsesCalendarBoundsForMonthQuarterYear() {
    LocalDate today = LocalDate.now(ZoneOffset.UTC);
    Instant monthStart = today.withDayOfMonth(1).atStartOfDay().toInstant(ZoneOffset.UTC);
    Instant yearStart = today.withDayOfYear(1).atStartOfDay().toInstant(ZoneOffset.UTC);
    Instant quarterStart =
        GraphTimeWindow.firstDayOfQuarter(today).atStartOfDay().toInstant(ZoneOffset.UTC);

    assertEquals(monthStart, GraphTimeWindow.startInstant("month"));
    assertEquals(quarterStart, GraphTimeWindow.startInstant("quarter"));
    assertEquals(yearStart, GraphTimeWindow.startInstant("year"));
    assertEquals(
        today.atStartOfDay().toInstant(ZoneOffset.UTC), GraphTimeWindow.startInstant("day"));
    assertEquals(
        today.atStartOfDay().toInstant(ZoneOffset.UTC), GraphTimeWindow.startInstant("today"));
    assertNull(GraphTimeWindow.startInstant("all"));
  }

  @Test
  void cypherFiltersCoverLongerWindows() {
    assertTrue(GraphTimeWindow.cypherTimestampFilter("day").contains("= date()"));
    assertTrue(GraphTimeWindow.cypherTimestampFilter("week").contains("P7D"));
    assertTrue(GraphTimeWindow.cypherTimestampFilter("month").contains("truncate('month'"));
    assertTrue(GraphTimeWindow.cypherTimestampFilter("quarter").contains("truncate('quarter'"));
    assertTrue(GraphTimeWindow.cypherTimestampFilter("year").contains("truncate('year'"));
    assertEquals("", GraphTimeWindow.cypherTimestampFilter("all"));
  }

  @Test
  void periodWording() {
    assertEquals(" today", GraphTimeWindow.periodSuffix("day"));
    assertEquals(" this month", GraphTimeWindow.periodSuffix("month"));
    assertEquals(" this quarter", GraphTimeWindow.periodSuffix("quarter"));
    assertEquals(" this year", GraphTimeWindow.periodSuffix("year"));
    assertEquals("this week", GraphTimeWindow.periodWord("week"));
    assertEquals("all time", GraphTimeWindow.periodWord("all"));
  }

  @Test
  void firstDayOfQuarter() {
    assertEquals(LocalDate.of(2026, 1, 1), GraphTimeWindow.firstDayOfQuarter(LocalDate.of(2026, 2, 15)));
    assertEquals(LocalDate.of(2026, 4, 1), GraphTimeWindow.firstDayOfQuarter(LocalDate.of(2026, 5, 1)));
    assertEquals(LocalDate.of(2026, 7, 1), GraphTimeWindow.firstDayOfQuarter(LocalDate.of(2026, 7, 23)));
    assertEquals(LocalDate.of(2026, 10, 1), GraphTimeWindow.firstDayOfQuarter(LocalDate.of(2026, 12, 31)));
  }

  @Test
  void weekStartIsRecentRollingBound() {
    Instant start = GraphTimeWindow.startInstant("week");
    assertNotNull(start);
    assertTrue(start.isBefore(Instant.now()));
    assertTrue(start.isAfter(Instant.now().minusSeconds(8L * 24 * 60 * 60)));
  }
}
