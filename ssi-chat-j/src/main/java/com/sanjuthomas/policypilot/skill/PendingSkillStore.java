package com.sanjuthomas.policypilot.skill;

import java.util.Iterator;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

/**
 * In-process TTL store for awaiting-confirmation skill runs (600s default). Keyed by a random
 * pending id; the confirming endpoint knows the skill, so one store namespaces by pending id.
 * Mirrors Python {@code chat_application.skills.pending_store.PendingSkillStore}.
 */
@Component
public class PendingSkillStore {

  static final long DEFAULT_TTL_MILLIS = 600_000L;

  private final Map<String, PendingSkill> items = new ConcurrentHashMap<>();

  public String newPendingId() {
    return UUID.randomUUID().toString();
  }

  public long defaultExpiresAt() {
    return System.currentTimeMillis() + DEFAULT_TTL_MILLIS;
  }

  public PendingSkill put(PendingSkill pending) {
    purgeExpired();
    items.put(pending.pendingId(), pending);
    return pending;
  }

  public PendingSkill get(String pendingId) {
    purgeExpired();
    return pendingId == null ? null : items.get(pendingId);
  }

  public PendingSkill pop(String pendingId) {
    purgeExpired();
    return pendingId == null ? null : items.remove(pendingId);
  }

  public void clear() {
    items.clear();
  }

  private void purgeExpired() {
    long now = System.currentTimeMillis();
    Iterator<Map.Entry<String, PendingSkill>> it = items.entrySet().iterator();
    while (it.hasNext()) {
      if (it.next().getValue().expiresAtEpochMs() <= now) {
        it.remove();
      }
    }
  }
}
