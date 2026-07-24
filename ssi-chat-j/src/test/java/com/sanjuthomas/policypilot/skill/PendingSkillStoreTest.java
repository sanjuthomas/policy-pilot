package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class PendingSkillStoreTest {

  private static PendingSkill pending(String id, long expiresAt) {
    ConfirmationCard card =
        new ConfirmationCard(
            "20260720-FICC-I-1",
            1_000_000d,
            "USD",
            "2026-07-21",
            "FICC",
            "APPROVED",
            null,
            null,
            null,
            null,
            List.of(),
            null,
            null);
    return new PendingSkill(
        id,
        "create_payment",
        "pay-101",
        null,
        "20260720-FICC-I-1",
        1_000_000d,
        "2026-07-21",
        "USD",
        "FICC",
        null,
        "APPROVED",
        "2027-07-20",
        "STANDING",
        1,
        null,
        null,
        card,
        expiresAt);
  }

  @Test
  void putGetPopRoundTrip() {
    PendingSkillStore store = new PendingSkillStore();
    String id = store.newPendingId();
    assertNotNull(id);
    store.put(pending(id, store.defaultExpiresAt()));

    assertNotNull(store.get(id));
    assertEquals("pay-101", store.get(id).userId());

    PendingSkill popped = store.pop(id);
    assertNotNull(popped);
    assertNull(store.get(id));
    assertNull(store.pop(id));
  }

  @Test
  void nullIdsAreSafe() {
    PendingSkillStore store = new PendingSkillStore();
    assertNull(store.get(null));
    assertNull(store.pop(null));
  }

  @Test
  void expiredEntriesArePurgedOnAccess() {
    PendingSkillStore store = new PendingSkillStore();
    String id = store.newPendingId();
    store.put(pending(id, System.currentTimeMillis() - 1_000L));
    assertNull(store.get(id));
  }

  @Test
  void clearRemovesEntries() {
    PendingSkillStore store = new PendingSkillStore();
    String id = store.newPendingId();
    store.put(pending(id, store.defaultExpiresAt()));
    store.clear();
    assertNull(store.get(id));
    assertTrue(store.defaultExpiresAt() > System.currentTimeMillis());
  }
}
