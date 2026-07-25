package com.sanjuthomas.policypilot.observability;

import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Micrometer instruments for Vertex / Gemini calls from ssi-chat-j, aligned with Python {@code
 * telemetry.gen_ai} ({@code gen_ai.client.operation.duration} / {@code .count}).
 */
@Component
public class GenAiMetrics {

  private static final double[] DURATION_SLO_MS = {
    5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 20000, 30000
  };

  private final MeterRegistry meterRegistry;
  private final String defaultModel;

  public GenAiMetrics(
      MeterRegistry meterRegistry,
      @Value("${spring.ai.vertex.ai.gemini.chat.options.model:gemini-2.5-flash}")
          String defaultModel) {
    this.meterRegistry = meterRegistry;
    this.defaultModel = defaultModel == null || defaultModel.isBlank() ? "gemini-2.5-flash" : defaultModel;
  }

  public void recordSuccess(String operation, double durationMs) {
    record(operation, defaultModel, "success", durationMs);
  }

  public void recordError(String operation, double durationMs) {
    record(operation, defaultModel, "error", durationMs);
  }

  public void record(String operation, String model, String status, double durationMs) {
    String op = blankToDash(operation);
    String mdl = blankToDash(model);
    Tags durationTags =
        Tags.of(
            "gen_ai.system", "vertex_ai",
            "gen_ai.request.model", mdl,
            "gen_ai.operation.name", op);
    DistributionSummary.builder("gen_ai.client.operation.duration")
        .baseUnit("ms")
        .serviceLevelObjectives(DURATION_SLO_MS)
        .tags(durationTags)
        .register(meterRegistry)
        .record(durationMs);
    meterRegistry
        .counter(
            "gen_ai.client.operation.count",
            durationTags.and("gen_ai.response.status", blankToDash(status)))
        .increment();
  }

  private static String blankToDash(String value) {
    return value == null || value.isBlank() ? "-" : value;
  }
}
