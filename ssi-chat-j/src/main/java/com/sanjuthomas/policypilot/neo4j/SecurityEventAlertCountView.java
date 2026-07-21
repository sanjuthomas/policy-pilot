package com.sanjuthomas.policypilot.neo4j;

/** View model for {@code templates/answers/security-event-alert-count.md}. */
public record SecurityEventAlertCountView(
    long total, String scopePrefix, String eventLabel, String periodSuffix) {}
