package com.sanjuthomas.policypilot.neo4j;

/** View model for payment/instruction creator-by-id Thymeleaf answers. */
public record EntityCreatorByIdView(
    boolean missing, boolean noCreator, String entityId, String creatorDisplay) {}
