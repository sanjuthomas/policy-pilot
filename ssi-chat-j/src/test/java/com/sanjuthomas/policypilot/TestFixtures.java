package com.sanjuthomas.policypilot;

import com.sanjuthomas.policypilot.config.ChatJProperties;
import java.util.List;

public final class TestFixtures {

  private TestFixtures() {}

  public static ChatJProperties properties() {
    return new ChatJProperties(
        "http://payment:8093",
        "http://instruction:8000",
        "http://authz:8094",
        "http://cypher-builder:8097",
        "bolt://localhost:7687",
        "svc_chat",
        "Password1!",
        "multimodal_embedding",
        8,
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
        List.of(
            "COMPLIANCE_ANALYST",
            "COMPLIANCE_OFFICER",
            "PLATFORM_ADMIN",
            "PAYMENT_CREATOR",
            "FUNDING_APPROVER",
            "INSTRUCTION_CREATOR",
            "INSTRUCTION_APPROVER"));
  }

  public static ChatJProperties propertiesWithoutPat() {
    return new ChatJProperties(
        "http://payment:8093",
        "http://instruction:8000",
        "http://authz:8094",
        "http://cypher-builder:8097",
        "bolt://localhost:7687",
        "svc_chat",
        "Password1!",
        "multimodal_embedding",
        8,
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
        List.of(
            "COMPLIANCE_ANALYST",
            "COMPLIANCE_OFFICER",
            "PLATFORM_ADMIN",
            "PAYMENT_CREATOR",
            "FUNDING_APPROVER",
            "INSTRUCTION_CREATOR",
            "INSTRUCTION_APPROVER"));
  }

  public static ChatJProperties propertiesWithPatFile(String patFile) {
    return new ChatJProperties(
        "http://payment:8093",
        "http://instruction:8000",
        "http://authz:8094",
        "http://cypher-builder:8097",
        "bolt://localhost:7687",
        "svc_chat",
        "Password1!",
        "multimodal_embedding",
        8,
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
