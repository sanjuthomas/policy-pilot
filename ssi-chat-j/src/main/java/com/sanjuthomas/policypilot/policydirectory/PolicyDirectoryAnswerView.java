package com.sanjuthomas.policypilot.policydirectory;

import java.util.List;

/** View model for amount-club / LOB funding-approver directory answers. */
public record PolicyDirectoryAnswerView(
    List<String> groups,
    Double amount,
    boolean strictThreshold,
    String coveringLob,
    List<PolicyDirectoryMemberRow> members) {}
