package com.sanjuthomas.policypilot.neo4j;

import java.util.List;

/** View model for payment/instruction approval-lookup Thymeleaf answers. */
public record ApprovalLookupView(
    boolean missing,
    boolean notApproved,
    String entityNoun,
    String displayNoun,
    String entityId,
    String status,
    String who,
    String when,
    List<String> authLines) {}
