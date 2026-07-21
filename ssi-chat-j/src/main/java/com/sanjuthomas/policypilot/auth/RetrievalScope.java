package com.sanjuthomas.policypilot.auth;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Subject LOB scope for neo4j_direct / graph retrieval (parity with Python {@code
 * allowed_retrieval_lobs}).
 *
 * <ul>
 *   <li>{@code null} — unscoped (compliance / platform admin)
 *   <li>empty set — no LOB entitlement
 *   <li>non-empty — FO desk lob or MO covering_lobs
 * </ul>
 */
public final class RetrievalScope {

  private static final Set<String> COMPLIANCE_ROLES =
      Set.of("COMPLIANCE_ANALYST", "COMPLIANCE_OFFICER", "PLATFORM_ADMIN");

  private RetrievalScope() {}

  public static Set<String> allowedRetrievalLobs(Subject subject) {
    if (subject == null) {
      return null;
    }
    List<String> roles = subject.roles() == null ? List.of() : subject.roles();
    List<String> groups = subject.groups() == null ? List.of() : subject.groups();
    for (String role : roles) {
      if (role != null && COMPLIANCE_ROLES.contains(role)) {
        return null;
      }
    }
    for (String group : groups) {
      if (group != null && "COMPLIANCE".equalsIgnoreCase(group)) {
        return null;
      }
    }
    for (String group : groups) {
      if (group != null && "MIDDLE_OFFICE".equalsIgnoreCase(group)) {
        Set<String> covering = new LinkedHashSet<>();
        if (subject.coveringLobs() != null) {
          for (String lob : subject.coveringLobs()) {
            if (lob != null && !lob.isBlank()) {
              covering.add(lob.strip().toUpperCase(Locale.ROOT));
            }
          }
        }
        return covering;
      }
    }
    if (subject.lob() != null && !subject.lob().isBlank()) {
      return Set.of(subject.lob().strip().toUpperCase(Locale.ROOT));
    }
    return Set.of();
  }
}
