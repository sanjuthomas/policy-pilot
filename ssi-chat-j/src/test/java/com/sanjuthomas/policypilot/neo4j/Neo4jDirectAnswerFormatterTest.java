package com.sanjuthomas.policypilot.neo4j;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class Neo4jDirectAnswerFormatterTest {

  private final Neo4jDirectAnswerFormatter formatter = new Neo4jDirectAnswerFormatter();

  @Test
  void formatsPluralAlertCountToday() {
    String answer =
        formatter.format(
            "How many ALERT events happened today?",
            Set.of("count", "details"),
            List.of(Map.of("total", 5)));
    assertEquals("There were 5 ALERT events today.", answer);
  }

  @Test
  void formatsSingularAndZero() {
    assertTrue(
        formatter
            .format("How many ALERT events happened today?", Set.of("count"), List.of(Map.of("total", 1)))
            .contains("1 ALERT event"));
    assertTrue(
        formatter
            .format("How many ALERT events happened today?", Set.of("count"), List.of())
            .contains("no ALERT events"));
  }

  @Test
  void formatsInstructionDenialWeek() {
    String answer =
        formatter.format(
            "How many instruction policy denials happened this week?",
            Set.of("count"),
            List.of(Map.of("total", 4)));
    assertEquals("There were 4 instruction policy denial events this week.", answer);
  }
}
