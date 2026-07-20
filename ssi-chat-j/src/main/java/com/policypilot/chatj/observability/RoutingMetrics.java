package com.policypilot.chatj.observability;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Emits the same chat routing Micrometer / OTLP series as Python {@code routing.py} for OpenSLO
 * parity ({@code chat.answer.count}, path decisions, retrieval/generation durations, …).
 */
@Component
public class RoutingMetrics {

  private static final Logger log = LoggerFactory.getLogger(RoutingMetrics.class);

  private final MeterRegistry meterRegistry;
  private final RoutingDistributionTracker distributionTracker;

  public RoutingMetrics(
      MeterRegistry meterRegistry, RoutingDistributionTracker distributionTracker) {
    this.meterRegistry = meterRegistry;
    this.distributionTracker = distributionTracker;
  }

  public void record(AnswerRouting routing) {
    String cypherClass = routing.cypherClass();
    Tags metricTags =
        Tags.of(
            "chat.retrieval_strategy", nullToDash(routing.retrievalStrategy()),
            "chat.cypher_class", cypherClass,
            "chat.cypher_provenance", nullToDash(routing.cypherProvenance()),
            "chat.path", nullToDash(routing.path()),
            "chat.mode", nullToDash(routing.mode()),
            "chat.answer_synthesis", nullToDash(routing.answerSynthesis()));

    meterRegistry.counter("chat.answer.count", metricTags).increment();
    meterRegistry.counter("chat.retrieval.route.count", metricTags).increment();

    Map<String, String> decision = routing.pathDecisionLabels();
    meterRegistry
        .counter(
            "chat.routing.path_decision.count",
            Tags.of(
                "chat.requested_path", decision.get("chat.requested_path"),
                "chat.executed_path", decision.get("chat.executed_path"),
                "chat.route_override", decision.get("chat.route_override"),
                "chat.mode", decision.get("chat.mode")))
        .increment();

    meterRegistry
        .counter(
            "chat.cypher.route.count",
            Tags.of(
                "chat.retrieval_strategy", nullToDash(routing.retrievalStrategy()),
                "chat.cypher_class", cypherClass,
                "chat.cypher_provenance", nullToDash(routing.cypherProvenance()),
                "chat.mode", nullToDash(routing.mode())))
        .increment();

    routing
        .sourceChannels()
        .forEach(
            (channel, count) -> {
              if (count != null && count > 0) {
                meterRegistry
                    .counter(
                        "chat.retrieval.source.channel.count",
                        Tags.of(
                            "chat.source_channel", channel,
                            "chat.retrieval_strategy", nullToDash(routing.retrievalStrategy()),
                            "chat.mode", nullToDash(routing.mode())))
                    .increment(count);
              }
            });

    if (routing.retrievalMs() != null) {
      meterRegistry
          .summary(
              "chat.answer.retrieval.duration",
              Tags.of(
                  "chat.retrieval_strategy", nullToDash(routing.retrievalStrategy()),
                  "chat.cypher_class", cypherClass,
                  "chat.path", nullToDash(routing.path()),
                  "chat.mode", nullToDash(routing.mode())))
          .record(routing.retrievalMs());
    }
    if (routing.generationMs() != null) {
      meterRegistry
          .summary(
              "chat.answer.generation.duration",
              Tags.of(
                  "chat.retrieval_strategy", nullToDash(routing.retrievalStrategy()),
                  "chat.cypher_class", cypherClass,
                  "chat.answer_synthesis", nullToDash(routing.answerSynthesis()),
                  "chat.mode", nullToDash(routing.mode())))
          .record(routing.generationMs());
    }

    distributionTracker.record(routing);

    String channelSummary =
        routing.sourceChannels().entrySet().stream()
            .filter(e -> e.getValue() != null && e.getValue() > 0)
            .map(e -> e.getKey() + "=" + e.getValue())
            .reduce((a, b) -> a + "," + b)
            .orElse("-");

    log.info(
        "chat.answer.completed strategy={} path={} requested={} override={} cypher={} "
            + "synthesis={} mode={} intent={} sources={} graph_rows={} channels={} "
            + "retrieval_ms={} generation_ms={}",
        routing.retrievalStrategy(),
        routing.path(),
        decision.get("chat.requested_path"),
        decision.get("chat.route_override"),
        routing.cypherProvenance(),
        routing.answerSynthesis(),
        routing.mode(),
        routing.intentId() == null ? "-" : routing.intentId(),
        routing.sourceCount(),
        routing.graphRowCount(),
        channelSummary,
        routing.retrievalMs(),
        routing.generationMs());
  }

  private static String nullToDash(String value) {
    return value == null || value.isBlank() ? "-" : value;
  }
}
