package com.sanjuthomas.policypilot.observability;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.stereotype.Component;

/** In-process feedback distribution for {@code GET /api/feedback-stats}. */
@Component
public class FeedbackDistributionTracker {

  private final AtomicLong up = new AtomicLong();
  private final AtomicLong down = new AtomicLong();
  private final ConcurrentHashMap<String, StrategyStats> byStrategy = new ConcurrentHashMap<>();
  private volatile Instant updatedAt;

  public void record(ChatFeedbackContext feedback) {
    StrategyStats stats =
        byStrategy.computeIfAbsent(feedback.retrievalStrategy(), k -> new StrategyStats());
    if ("up".equals(feedback.rating())) {
      up.incrementAndGet();
      stats.up.incrementAndGet();
    } else {
      down.incrementAndGet();
      stats.down.incrementAndGet();
    }
    updatedAt = Instant.now();
  }

  public Map<String, Object> snapshot() {
    long upCount = up.get();
    long downCount = down.get();
    long total = upCount + downCount;
    Map<String, Object> byStrategyOut = new LinkedHashMap<>();
    byStrategy.entrySet().stream()
        .sorted(Map.Entry.comparingByKey())
        .forEach(e -> byStrategyOut.put(e.getKey(), e.getValue().toMap()));

    Map<String, Object> out = new LinkedHashMap<>();
    out.put("total", total);
    out.put("up", upCount);
    out.put("down", downCount);
    out.put(
        "satisfaction_rate",
        total == 0 ? null : Math.round((upCount / (double) total) * 10000.0) / 10000.0);
    out.put("by_strategy", byStrategyOut);
    out.put("updated_at", updatedAt == null ? null : updatedAt.toString());
    return out;
  }

  public void reset() {
    up.set(0);
    down.set(0);
    byStrategy.clear();
    updatedAt = null;
  }

  private static final class StrategyStats {
    private final AtomicLong up = new AtomicLong();
    private final AtomicLong down = new AtomicLong();

    Map<String, Object> toMap() {
      long u = up.get();
      long d = down.get();
      long total = u + d;
      Map<String, Object> out = new LinkedHashMap<>();
      out.put("up", u);
      out.put("down", d);
      out.put("total", total);
      out.put(
          "satisfaction_rate",
          total == 0 ? null : Math.round((u / (double) total) * 10000.0) / 10000.0);
      return out;
    }
  }
}
