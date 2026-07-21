package com.sanjuthomas.policypilot.neo4j;

import java.util.List;

/** View model for payment/instruction approval-lookup Thymeleaf answers. */
public record ApprovalLookupView(
    boolean missing, String entityNoun, String who, String when, List<String> authLines) {}
