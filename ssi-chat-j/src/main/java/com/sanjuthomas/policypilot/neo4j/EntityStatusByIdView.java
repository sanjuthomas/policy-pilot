package com.sanjuthomas.policypilot.neo4j;

/** View model for payment/instruction status-by-id Thymeleaf answers. */
public record EntityStatusByIdView(
    boolean missing, String entityId, String status, String lobSuffix) {}
