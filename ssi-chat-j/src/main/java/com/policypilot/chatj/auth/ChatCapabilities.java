package com.policypilot.chatj.auth;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Derived chat capabilities from the logged-in subject's roles/groups. */
public record ChatCapabilities(
    boolean compliance,
    boolean canCreatePayment,
    boolean canApprovePayment,
    boolean canCancelPayment) {

  private static final Set<String> COMPLIANCE =
      Set.of("COMPLIANCE_ANALYST", "COMPLIANCE_OFFICER", "PLATFORM_ADMIN");

  public static ChatCapabilities forSubject(Subject subject) {
    Set<String> roles = new HashSet<>(subject.roles() == null ? List.of() : subject.roles());
    Set<String> groups = new HashSet<>(subject.groups() == null ? List.of() : subject.groups());
    boolean creator = roles.contains("PAYMENT_CREATOR");
    return new ChatCapabilities(
        roles.stream().anyMatch(COMPLIANCE::contains),
        creator,
        roles.contains("FUNDING_APPROVER"),
        creator && groups.contains("MIDDLE_OFFICE"));
  }
}
