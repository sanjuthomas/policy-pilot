package com.sanjuthomas.policypilot.observability;

import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import org.springframework.stereotype.Component;

/**
 * Separates IntentRouter (LLM) time from path-lane work so Grafana can show why {@code
 * chat.answer.retrieval.duration} is large without blaming Mongo/OPA.
 */
@Component
public class ChatPhaseMetrics {

  private static final double[] DURATION_SLO_MS = {
    5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 20000, 30000
  };

  private final MeterRegistry meterRegistry;

  public ChatPhaseMetrics(MeterRegistry meterRegistry) {
    this.meterRegistry = meterRegistry;
  }

  public void recordRouter(String path, double durationMs) {
    record("chat.router.duration", path, durationMs);
  }

  public void recordLane(String path, double durationMs) {
    record("chat.lane.duration", path, durationMs);
  }

  private void record(String metric, String path, double durationMs) {
    DistributionSummary.builder(metric)
        .baseUnit("ms")
        .serviceLevelObjectives(DURATION_SLO_MS)
        .tags(Tags.of("chat.path", path == null || path.isBlank() ? "-" : path))
        .register(meterRegistry)
        .record(durationMs);
  }
}
