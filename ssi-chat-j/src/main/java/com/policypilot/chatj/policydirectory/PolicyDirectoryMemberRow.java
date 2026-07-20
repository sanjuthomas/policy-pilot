package com.policypilot.chatj.policydirectory;

import java.util.List;

/** One directory member row for the policy-directory answer table. */
public record PolicyDirectoryMemberRow(
    String userId, String displayName, String title, String groups, String coveringLobs) {}
