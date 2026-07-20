package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.LobFilterParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.util.Locale;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Build {@link MeIntent} from Spring AI {@link RouterDecision} + deterministic slot parsers. */
@Component
public class MeIntentResolver {

  private static final Pattern CREATE_OR_DRAFT =
      Pattern.compile("\\b(create|draft)\\b", Pattern.CASE_INSENSITIVE);

  public MeIntent resolve(RouterDecision decision, String message) {
    if (decision == null || !"me".equalsIgnoreCase(nullToEmpty(decision.getPath()))) {
      return null;
    }
    String kind =
        StringUtils.hasText(decision.getMeKind())
            ? decision.getMeKind().strip().toLowerCase(Locale.ROOT)
            : "who_am_i";

    String text = message == null ? "" : message.strip();
    String entityId = PaymentIdParser.extract(text).orElse(null);
    String coveringLob = LobFilterParser.extract(text).orElse(null);
    String action =
        StringUtils.hasText(decision.getMeAction())
            ? decision.getMeAction().strip().toUpperCase(Locale.ROOT)
            : null;
    String entityType =
        StringUtils.hasText(decision.getMeEntityType())
            ? decision.getMeEntityType().strip().toLowerCase(Locale.ROOT)
            : null;

    return switch (kind) {
      case "who_can_create" -> {
        String resolvedType = entityType != null ? entityType : createEntityType(text);
        if (resolvedType == null) {
          yield null;
        }
        yield new MeIntent(
            kind, action != null ? action : "CREATE", resolvedType, null, coveringLob);
      }
      case "who_covers_lob" -> {
        if (CREATE_OR_DRAFT.matcher(text).find()) {
          String resolvedType = entityType != null ? entityType : createEntityType(text);
          yield new MeIntent(
              "who_can_create",
              "CREATE",
              resolvedType != null ? resolvedType : "payment",
              null,
              coveringLob);
        }
        yield new MeIntent(kind, null, null, null, coveringLob);
      }
      case "can_act_on_entity" ->
          new MeIntent(
              kind,
              action != null ? action : "CREATE",
              entityType != null ? entityType : "payment",
              entityId,
              null);
      case "who_else_can_act" ->
          new MeIntent(
              kind,
              action != null ? action : "APPROVE",
              entityType != null ? entityType : "payment",
              entityId,
              null);
      case "waiting_for_me" ->
          new MeIntent(
              kind,
              action != null ? action : "APPROVE",
              entityType != null ? entityType : "payment",
              null,
              null);
      default -> new MeIntent(kind, action, entityType, entityId, coveringLob);
    };
  }

  private static String createEntityType(String text) {
    String lower = text.toLowerCase(Locale.ROOT);
    if (lower.contains("instruction")) {
      return "instruction";
    }
    if (lower.contains("payment")) {
      return "payment";
    }
    return null;
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
