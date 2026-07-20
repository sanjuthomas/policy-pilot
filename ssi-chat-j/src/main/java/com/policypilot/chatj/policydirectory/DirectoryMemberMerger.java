package com.policypilot.chatj.policydirectory;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/** Deduplicate group-member rows by {@code user_id} (union across clubs). */
public final class DirectoryMemberMerger {

  private DirectoryMemberMerger() {}

  @SuppressWarnings("unchecked")
  public static List<Map<String, Object>> merge(List<Map<String, Object>> members) {
    Map<String, Map<String, Object>> byId = new LinkedHashMap<>();
    for (Map<String, Object> row : members) {
      if (row == null) {
        continue;
      }
      Object userIdObj = row.get("user_id");
      if (userIdObj == null || String.valueOf(userIdObj).isBlank()) {
        continue;
      }
      String userId = String.valueOf(userIdObj);
      if (!byId.containsKey(userId)) {
        byId.put(userId, new LinkedHashMap<>(row));
        continue;
      }
      Map<String, Object> existing = byId.get(userId);
      for (String key : List.of("groups", "covering_lobs", "roles")) {
        existing.put(key, unionLists(existing.get(key), row.get(key)));
      }
    }
    return new ArrayList<>(byId.values());
  }

  @SuppressWarnings("unchecked")
  private static List<String> unionLists(Object left, Object right) {
    TreeSet<String> merged = new TreeSet<>();
    addAll(merged, left);
    addAll(merged, right);
    return new ArrayList<>(merged);
  }

  private static void addAll(TreeSet<String> target, Object value) {
    if (value instanceof List<?> list) {
      for (Object item : list) {
        if (item != null && !String.valueOf(item).isBlank()) {
          target.add(String.valueOf(item));
        }
      }
    }
  }
}
