package com.sanjuthomas.policypilot.neo4j;

/** View model for creator+approver-by-id Thymeleaf answers (Python parity). */
public record EntityCreatorAndApproverView(
    boolean missing,
    String displayNoun,
    String entityNoun,
    String entityId,
    String creatorDisplay,
    String approverDisplay,
    String approvedAt) {}
