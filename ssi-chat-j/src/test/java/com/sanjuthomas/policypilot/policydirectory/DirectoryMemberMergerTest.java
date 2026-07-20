package com.sanjuthomas.policypilot.policydirectory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class DirectoryMemberMergerTest {

  @Test
  void deduplicatesByUserIdAndUnionsGroups() {
    List<Map<String, Object>> merged =
        DirectoryMemberMerger.merge(
            List.of(
                Map.of("user_id", "pay-201", "groups", List.of("MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB")),
                Map.of("user_id", "pay-201", "groups", List.of("MIDDLE_OFFICE")),
                Map.of(
                    "user_id",
                    "pay-204",
                    "groups",
                    List.of("MIDDLE_OFFICE", "UP_TO_100_BILLION_CLUB"))));
    assertEquals(List.of("pay-201", "pay-204"), merged.stream().map(r -> r.get("user_id")).toList());
    @SuppressWarnings("unchecked")
    List<String> groups = (List<String>) merged.get(0).get("groups");
    assertTrue(groups.contains("UP_TO_1_BILLION_CLUB"));
  }
}
