package com.sanjuthomas.policypilot.auth;

import java.util.List;

/** Full directory row from the ZITADEL seed (classpath {@code users.yaml}). */
public record DirectoryUser(
    String userId,
    String givenName,
    String familyName,
    String title,
    String lob,
    List<String> roles,
    List<String> groups,
    List<String> coveringLobs,
    String supervisorId) {

  public String displayName() {
    if (familyName != null
        && !familyName.isBlank()
        && givenName != null
        && !givenName.isBlank()) {
      return familyName + ", " + givenName;
    }
    return userId;
  }
}
