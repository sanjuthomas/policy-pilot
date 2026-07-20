package com.policypilot.chatj.observability;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.stereotype.Component;

/** In-process routing distribution for {@code GET /api/routing-stats} (parity with Python). */
@Component
public class RoutingDistributionTracker {

  private final AtomicLong total = new AtomicLong();
  private final AtomicLong routeOverrideTotal = new AtomicLong();
  private final AtomicLong routeHonoredTotal = new AtomicLong();
  private final ConcurrentHashMap<String, AtomicLong> byStrategy = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, AtomicLong> byPath = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, AtomicLong> byCypherClass = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, AtomicLong> bySynthesis = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, AtomicLong> byMode = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, AtomicLong> bySourceChannel = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, AtomicLong> byPathPair = new ConcurrentHashMap<>();
  private volatile Instant updatedAt;

  public void record(AnswerRouting routing) {
    Map<String, String> labels = routing.pathDecisionLabels();
    String pair =
        ChatObservability.pathPairKey(
            labels.get("chat.requested_path"), labels.get("chat.executed_path"));
    boolean overridden = "true".equals(labels.get("chat.route_override"));

    total.incrementAndGet();
    bump(byStrategy, routing.retrievalStrategy());
    bump(byPath, routing.path());
    bump(byCypherClass, routing.cypherClass());
    bump(bySynthesis, routing.answerSynthesis());
    bump(byMode, routing.mode());
    bump(byPathPair, pair);
    if (overridden) {
      routeOverrideTotal.incrementAndGet();
    } else {
      routeHonoredTotal.incrementAndGet();
    }
    routing
        .sourceChannels()
        .forEach(
            (channel, count) -> {
              if (count != null && count > 0) {
                bySourceChannel
                    .computeIfAbsent(channel, k -> new AtomicLong())
                    .addAndGet(count);
              }
            });
    updatedAt = Instant.now();
  }

  public Map<String, Object> snapshot() {
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("total", total.get());
    out.put("by_strategy", copy(byStrategy));
    out.put("by_path", copy(byPath));
    out.put("by_cypher_class", copy(byCypherClass));
    out.put("by_synthesis", copy(bySynthesis));
    out.put("by_mode", copy(byMode));
    out.put("by_source_channel", copy(bySourceChannel));
    out.put("route_override_total", routeOverrideTotal.get());
    out.put("route_honored_total", routeHonoredTotal.get());
    out.put("by_path_pair", copy(byPathPair));
    out.put("updated_at", updatedAt == null ? null : updatedAt.toString());
    return out;
  }

  public void reset() {
    total.set(0);
    routeOverrideTotal.set(0);
    routeHonoredTotal.set(0);
    byStrategy.clear();
    byPath.clear();
    byCypherClass.clear();
    bySynthesis.clear();
    byMode.clear();
    bySourceChannel.clear();
    byPathPair.clear();
    updatedAt = null;
  }

  private static void bump(ConcurrentHashMap<String, AtomicLong> map, String key) {
    if (key == null || key.isBlank()) {
      return;
    }
    map.computeIfAbsent(key, k -> new AtomicLong()).incrementAndGet();
  }

  private static Map<String, Long> copy(ConcurrentHashMap<String, AtomicLong> map) {
    Map<String, Long> out = new LinkedHashMap<>();
    map.forEach((k, v) -> out.put(k, v.get()));
    return out;
  }
}
