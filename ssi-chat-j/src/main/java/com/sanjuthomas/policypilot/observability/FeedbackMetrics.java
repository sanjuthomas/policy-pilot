package com.sanjuthomas.policypilot.observability;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/** Emits {@code chat.feedback.count} for the non-downvote OpenSLO SLI. */
@Component
public class FeedbackMetrics {

  private static final Logger log = LoggerFactory.getLogger(FeedbackMetrics.class);

  private final MeterRegistry meterRegistry;
  private final FeedbackDistributionTracker distributionTracker;

  public FeedbackMetrics(
      MeterRegistry meterRegistry, FeedbackDistributionTracker distributionTracker) {
    this.meterRegistry = meterRegistry;
    this.distributionTracker = distributionTracker;
  }

  public void record(ChatFeedbackContext feedback) {
    String cypherClass = ChatObservability.cypherClassForProvenance(feedback.cypherProvenance());
    meterRegistry
        .counter(
            "chat.feedback.count",
            Tags.of(
                "chat.feedback_rating", feedback.rating(),
                "chat.retrieval_strategy", feedback.retrievalStrategy(),
                "chat.path", feedback.path(),
                "chat.mode", feedback.mode(),
                "chat.cypher_class", cypherClass,
                "chat.answer_synthesis", feedback.answerSynthesis()))
        .increment();
    distributionTracker.record(feedback);
    log.info(
        "chat.feedback.received rating={} strategy={} path={} cypher={} synthesis={} mode={} user={}",
        feedback.rating(),
        feedback.retrievalStrategy(),
        feedback.path(),
        feedback.cypherProvenance(),
        feedback.answerSynthesis(),
        feedback.mode(),
        feedback.userId() == null ? "-" : feedback.userId());
  }
}
