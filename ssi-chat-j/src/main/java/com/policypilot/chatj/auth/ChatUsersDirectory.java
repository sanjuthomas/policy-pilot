package com.policypilot.chatj.auth;

import com.policypilot.chatj.config.ChatJProperties;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.yaml.snakeyaml.Yaml;

/**
 * Login-picker roster from the ZITADEL seed file (build-time copy of {@code zitadel-seed/users.yaml}).
 *
 * <p>M1 uses the seed as a stable directory for the UI; live ZITADEL list can replace this later.
 */
@Component
public class ChatUsersDirectory {

  private final ChatJProperties properties;

  public ChatUsersDirectory(ChatJProperties properties) {
    this.properties = properties;
  }

  public List<Map<String, Object>> listChatUsers() {
    Set<String> allowed = new HashSet<>(properties.chatRoles());
    List<Map<String, Object>> rows = new ArrayList<>();
    for (Map<String, Object> user : loadSeedUsers()) {
      String userId = str(user.get("user_id"));
      if (userId.startsWith("svc-")) {
        continue;
      }
      List<String> roles = stringList(user.get("roles"));
      if (roles.stream().noneMatch(allowed::contains)) {
        continue;
      }
      Map<String, Object> row = new LinkedHashMap<>();
      row.put("user_id", userId);
      row.put(
          "display_name",
          str(user.get("family_name")) + ", " + str(user.get("given_name")));
      row.put("title", str(user.get("title")));
      row.put("roles", roles);
      row.put("audiences", AudienceLabels.forRoles(roles));
      rows.add(row);
    }
    rows.sort(Comparator.comparing(r -> String.valueOf(r.get("display_name"))));
    return rows;
  }

  @SuppressWarnings("unchecked")
  private List<Map<String, Object>> loadSeedUsers() {
    try (InputStream in = new ClassPathResource("users.yaml").getInputStream()) {
      Object doc = new Yaml().load(in);
      if (!(doc instanceof Map<?, ?> map)) {
        return List.of();
      }
      Object users = map.get("users");
      if (!(users instanceof List<?> list)) {
        return List.of();
      }
      List<Map<String, Object>> out = new ArrayList<>();
      for (Object item : list) {
        if (item instanceof Map<?, ?> m) {
          out.add((Map<String, Object>) m);
        }
      }
      return out;
    } catch (Exception ex) {
      throw new IllegalStateException("failed to load classpath:users.yaml", ex);
    }
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }

  @SuppressWarnings("unchecked")
  private static List<String> stringList(Object value) {
    if (!(value instanceof List<?> list)) {
      return List.of();
    }
    List<String> out = new ArrayList<>();
    for (Object item : list) {
      if (item != null) {
        out.add(String.valueOf(item));
      }
    }
    return out;
  }
}
