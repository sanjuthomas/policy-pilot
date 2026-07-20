package com.policypilot.chatj.auth;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** Human-readable audience tags for the login picker (parity with Python {@code audience_labels}). */
public final class AudienceLabels {

  private static final Set<String> COMPLIANCE =
      Set.of("COMPLIANCE_ANALYST", "COMPLIANCE_OFFICER", "PLATFORM_ADMIN");

  private AudienceLabels() {}

  public static List<String> forRoles(List<String> roles) {
    Set<String> roleSet = Set.copyOf(roles);
    List<String> labels = new ArrayList<>();
    if (roleSet.stream().anyMatch(COMPLIANCE::contains)) {
      labels.add("compliance");
    }
    if (roleSet.contains("PAYMENT_CREATOR")) {
      labels.add("payment_creator");
    }
    if (roleSet.contains("FUNDING_APPROVER")) {
      labels.add("funding_approver");
    }
    if (roleSet.contains("INSTRUCTION_CREATOR")) {
      labels.add("instruction_creator");
    }
    if (roleSet.contains("INSTRUCTION_APPROVER")) {
      labels.add("instruction_approver");
    }
    return labels;
  }
}
