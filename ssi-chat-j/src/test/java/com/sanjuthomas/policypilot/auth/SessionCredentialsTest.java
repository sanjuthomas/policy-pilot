package com.sanjuthomas.policypilot.auth;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class SessionCredentialsTest {

  @Test
  void recordStoresSessionFields() {
    SessionCredentials credentials = new SessionCredentials("sess-1", "tok-1", "alice");
    assertEquals("sess-1", credentials.sessionId());
    assertEquals("tok-1", credentials.sessionToken());
    assertEquals("alice", credentials.userId());
  }
}
