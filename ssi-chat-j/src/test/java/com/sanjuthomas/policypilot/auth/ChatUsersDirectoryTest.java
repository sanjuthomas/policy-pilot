package com.sanjuthomas.policypilot.auth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.TestFixtures;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ChatUsersDirectoryTest {

  @Test
  void listChatUsersFiltersSvcAndSortsByDisplayName() {
    ChatUsersDirectory directory = new ChatUsersDirectory(TestFixtures.properties());
    List<Map<String, Object>> users = directory.listChatUsers();
    assertFalse(users.isEmpty());
    assertTrue(users.stream().noneMatch(u -> String.valueOf(u.get("user_id")).startsWith("svc-")));
    for (int i = 1; i < users.size(); i++) {
      String prev = String.valueOf(users.get(i - 1).get("display_name"));
      String cur = String.valueOf(users.get(i).get("display_name"));
      assertTrue(prev.compareTo(cur) <= 0, prev + " before " + cur);
    }
    Map<String, Object> first = users.get(0);
    assertTrue(first.containsKey("audiences"));
    assertTrue(first.containsKey("roles"));
  }
}

class AudienceLabelsTest {

  @Test
  void mapsComplianceAndOperationalRoles() {
    assertEquals(List.of("compliance"), AudienceLabels.forRoles(List.of("PLATFORM_ADMIN")));
    assertEquals(
        List.of("payment_creator", "funding_approver"),
        AudienceLabels.forRoles(List.of("PAYMENT_CREATOR", "FUNDING_APPROVER")));
  }
}
