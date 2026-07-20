package com.sanjuthomas.policypilot.auth;

import java.util.List;

public record Subject(
    String userId,
    String givenName,
    String familyName,
    String title,
    String lob,
    List<String> roles,
    List<String> groups,
    String supervisorId,
    List<String> coveringLobs,
    String bearerToken,
    String sessionId) {

  public Subject withTokens(String bearerToken, String sessionId) {
    return new Subject(
        userId,
        givenName,
        familyName,
        title,
        lob,
        roles,
        groups,
        supervisorId,
        coveringLobs,
        bearerToken,
        sessionId);
  }
}
