package com.policypilot.chatj.config;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.TestFixtures;
import com.policypilot.chatj.config.AppConfig.ZitadelPatProvider;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.web.client.RestTemplateBuilder;

class AppConfigTest {

  @Test
  void hasChatRole() {
    assertTrue(AppConfig.hasChatRole(List.of("PAYMENT_CREATOR"), List.of("PAYMENT_CREATOR")));
    assertFalse(AppConfig.hasChatRole(List.of("OTHER"), List.of("PAYMENT_CREATOR")));
    assertFalse(AppConfig.hasChatRole(null, List.of("PAYMENT_CREATOR")));
    assertFalse(AppConfig.hasChatRole(List.of("PAYMENT_CREATOR"), null));
  }

  @Test
  void patProviderReadsInlinePat() {
    ZitadelPatProvider provider = new ZitadelPatProvider(TestFixtures.properties());
    assertEquals("test-pat", provider.get());
    assertEquals("test-pat", provider.get()); // cached
  }

  @Test
  void patProviderReadsFile(@TempDir Path dir) throws Exception {
    Path pat = dir.resolve("login-client.pat");
    Files.writeString(pat, " file-pat \n");
    ZitadelPatProvider provider =
        new ZitadelPatProvider(TestFixtures.propertiesWithPatFile(pat.toString()));
    assertEquals("file-pat", provider.get());
  }

  @Test
  void patProviderFailsOnMissingFile() {
    ZitadelPatProvider provider =
        new ZitadelPatProvider(TestFixtures.propertiesWithPatFile("/no/such/pat"));
    assertThrows(IllegalStateException.class, provider::get);
  }

  @Test
  void restTemplateBeanBuilds() {
    AppConfig config = new AppConfig();
    assertTrue(config.restTemplate(new RestTemplateBuilder()) != null);
    assertTrue(config.zitadelPatProvider(TestFixtures.properties()) != null);
  }
}
