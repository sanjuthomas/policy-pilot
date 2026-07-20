package com.policypilot.chatj;

import com.policypilot.chatj.config.ChatJProperties;
import java.util.List;

public final class TestFixtures {

  private TestFixtures() {}

  public static ChatJProperties properties() {
    return new ChatJProperties(
        "http://payment:8093",
        "http://instruction:8000",
        "http://authz:8094",
        "http://zitadel:8080",
        "http://zitadel-internal:8080",
        "localhost",
        "test-pat",
        "",
        "http://localhost:8080",
        "http://zitadel-internal:8080",
        "policy-pilot",
        "ssi.local",
        "svc-chat",
        "Password1!",
        List.of("COMPLIANCE_ANALYST", "PAYMENT_CREATOR"));
  }

  public static ChatJProperties propertiesWithoutPat() {
    return new ChatJProperties(
        "http://payment:8093",
        "http://instruction:8000",
        "http://authz:8094",
        "http://zitadel:8080",
        "http://zitadel-internal:8080",
        "localhost",
        "",
        "",
        "http://localhost:8080",
        "http://zitadel-internal:8080",
        "policy-pilot",
        "ssi.local",
        "svc-chat",
        "Password1!",
        List.of("COMPLIANCE_ANALYST", "PAYMENT_CREATOR"));
  }

  public static ChatJProperties propertiesWithPatFile(String patFile) {
    return new ChatJProperties(
        "http://payment:8093",
        "http://instruction:8000",
        "http://authz:8094",
        "http://zitadel:8080",
        "",
        "localhost",
        "",
        patFile,
        "http://localhost:8080",
        "",
        "policy-pilot",
        "ssi.local",
        "svc-chat",
        "Password1!",
        List.of("COMPLIANCE_ANALYST"));
  }
}
