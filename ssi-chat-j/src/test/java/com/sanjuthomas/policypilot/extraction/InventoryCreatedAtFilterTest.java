package com.sanjuthomas.policypilot.extraction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class InventoryCreatedAtFilterTest {

  @Test
  void keepsRowsInsideTodayWindow() {
    Instant now = Instant.now();
    List<Map<String, Object>> rows =
        List.of(
            Map.of("id", "new", "created_at", now.toString()),
            Map.of("id", "old", "created_at", "2020-01-01T00:00:00Z"));

    List<Map<String, Object>> filtered = InventoryCreatedAtFilter.apply(rows, "today");

    assertEquals(1, filtered.size());
    assertEquals("new", filtered.get(0).get("id"));
  }

  @Test
  void weekWindowKeepsRecentRows() {
    Instant recent = Instant.now().minusSeconds(2 * 24 * 60 * 60);
    Instant old = Instant.now().minusSeconds(30L * 24 * 60 * 60);
    List<Map<String, Object>> rows =
        List.of(
            Map.of("id", "recent", "created_at", recent.toString()),
            Map.of("id", "old", "created_at", old.toString()));

    List<Map<String, Object>> filtered = InventoryCreatedAtFilter.apply(rows, "week");

    assertEquals(1, filtered.size());
    assertEquals("recent", filtered.get(0).get("id"));
  }

  @Test
  void monthWindowKeepsCurrentMonthRows() {
    Instant now = Instant.now();
    List<Map<String, Object>> rows =
        List.of(
            Map.of("id", "current", "created_at", now.toString()),
            Map.of("id", "old", "created_at", "2020-01-01T00:00:00Z"));

    List<Map<String, Object>> filtered = InventoryCreatedAtFilter.apply(rows, "month");
    assertEquals(1, filtered.size());
    assertEquals("current", filtered.get(0).get("id"));
  }

  @Test
  void dayAliasTodayBehavesTheSame() {
    Instant now = Instant.now();
    List<Map<String, Object>> rows =
        List.of(
            Map.of("id", "new", "created_at", now.toString()),
            Map.of("id", "old", "created_at", "2020-01-01T00:00:00Z"));
    assertEquals(
        InventoryCreatedAtFilter.apply(rows, "day").size(),
        InventoryCreatedAtFilter.apply(rows, "today").size());
  }

  @Test
  void blankWindowReturnsAll() {
    List<Map<String, Object>> rows = List.of(Map.of("id", "a", "created_at", "2020-01-01T00:00:00Z"));
    assertEquals(1, InventoryCreatedAtFilter.apply(rows, null).size());
    assertEquals(1, InventoryCreatedAtFilter.apply(rows, "all").size());
  }

  @Test
  void parsesInstantInstanceAndBareIsoWithoutZ() {
    Instant now = Instant.now();
    List<Map<String, Object>> rows =
        List.of(
            Map.of("id", "inst", "created_at", now),
            Map.of("id", "bare", "created_at", now.toString().replace("Z", "")),
            Map.of("id", "bad", "created_at", "not-a-date"),
            Map.of("id", "old", "created_at", "2020-01-01T00:00:00Z"));

    List<Map<String, Object>> filtered = InventoryCreatedAtFilter.apply(rows, "today");
    // Unparseable timestamps are kept; only clearly-old timestamps drop out.
    assertEquals(3, filtered.size());
  }

  @Test
  void nullRowsSafe() {
    assertTrue(InventoryCreatedAtFilter.apply(null, "today").isEmpty());
  }
}
