package com.sanjuthomas.policypilot.auth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class SubjectResolverTest {

  @Test
  void resolveRequiresBearerToken() {
    SubjectResolver subjectResolver = new SubjectResolver(new FakeZitadelAuthClient());
    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class, () -> subjectResolver.resolve("", "sess"));
    assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
  }

  @Test
  void resolveRequiresSessionId() {
    SubjectResolver subjectResolver = new SubjectResolver(new FakeZitadelAuthClient());
    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class, () -> subjectResolver.resolve("tok", ""));
    assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
  }

  @Test
  void resolveBuildsSubjectFromSessionAndMetadata() {
    FakeZitadelAuthClient zitadel =
        new FakeZitadelAuthClient()
            .onGetSession(
                (sessionId, token) ->
                    Map.of(
                        "session",
                        Map.of(
                            "factors",
                            Map.of(
                                "user",
                                Map.of("id", "z-1", "loginName", "comp-001@ssi.local")))))
            .onFetchMetadata(
                userId ->
                    Map.of(
                        "title",
                        "Analyst",
                        "roles",
                        "[\"COMPLIANCE_ANALYST\"]",
                        "groups",
                        "[\"FICC\"]",
                        "covering_lobs",
                        "[\"EM\"]",
                        "given_name",
                        "Comp",
                        "family_name",
                        "One",
                        "lob",
                        "FICC",
                        "supervisor_id",
                        "sup-1"));
    SubjectResolver subjectResolver = new SubjectResolver(zitadel);

    Subject subject = subjectResolver.resolve("tok-1", "sess-1");

    assertEquals("comp-001", subject.userId());
    assertEquals("Analyst", subject.title());
    assertEquals(List.of("COMPLIANCE_ANALYST"), subject.roles());
    assertEquals("tok-1", subject.bearerToken());
    assertEquals("sess-1", subject.sessionId());
  }

  @Test
  void resolveMapsSessionErrorsToUnauthorized() {
    FakeZitadelAuthClient zitadel =
        new FakeZitadelAuthClient().onGetSession((sessionId, token) -> Map.of("unexpected", true));
    SubjectResolver subjectResolver = new SubjectResolver(zitadel);

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class, () -> subjectResolver.resolve("tok-1", "sess-1"));
    assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
  }

  @Test
  void fromMetadataUsesFallbackUserIdAndStripsDomain() {
    Subject subject =
        SubjectResolver.fromMetadata(
            Map.of(
                "title",
                "FO",
                "roles",
                "FUNDING_APPROVER,PAYMENT_CREATOR",
                "subject_user_id",
                "pay-101@ssi.local"),
            "fallback");

    assertEquals("pay-101", subject.userId());
    assertEquals(List.of("FUNDING_APPROVER", "PAYMENT_CREATOR"), subject.roles());
  }

  @Test
  void fromMetadataValidatesRequiredFields() {
    assertThrows(
        IllegalArgumentException.class,
        () -> SubjectResolver.fromMetadata(Map.of("title", "FO"), ""));
    assertThrows(
        IllegalArgumentException.class,
        () -> SubjectResolver.fromMetadata(Map.of("roles", "[\"X\"]"), "user-1"));
    assertThrows(
        IllegalArgumentException.class,
        () ->
            SubjectResolver.fromMetadata(
                Map.of("title", "FO", "roles", "[]"), "user-1"));
  }
}
