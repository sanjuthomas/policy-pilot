package com.policypilot.chatj.auth;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public class FakeSubjectResolver extends SubjectResolver {

  private Subject subject;
  private ResponseStatusException error;

  public FakeSubjectResolver(ZitadelAuthClient client) {
    super(client);
  }

  public FakeSubjectResolver returning(Subject subject) {
    this.subject = subject;
    return this;
  }

  public FakeSubjectResolver failing(ResponseStatusException error) {
    this.error = error;
    return this;
  }

  @Override
  public Subject resolve(String bearerToken, String sessionId) {
    if (error != null) {
      throw error;
    }
    if (subject != null) {
      return subject;
    }
    return super.resolve(bearerToken, sessionId);
  }
}
