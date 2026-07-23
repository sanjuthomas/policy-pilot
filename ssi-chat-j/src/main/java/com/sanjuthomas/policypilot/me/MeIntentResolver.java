package com.sanjuthomas.policypilot.me;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.LobFilterParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.util.Locale;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * Build {@link MeIntent} from Spring AI {@link RouterDecision} + stable-token parsers (ids, LOB).
 *
 * <p>{@code meKind} / {@code meAction} / {@code meEntityType} come from the router — do not rewrite
 * kinds from create/draft phrasing.
 */
@Component
public class MeIntentResolver {

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
        if (entityType == null) {
          yield null;
        }
        yield new MeIntent(
            kind, action != null ? action : "CREATE", entityType, null, coveringLob);
      }
      case "who_covers_lob" -> new MeIntent(kind, null, null, null, coveringLob);
      case "can_act_on_entity" ->
          new MeIntent(
              kind,
              action != null ? action : "CREATE",
              entityType != null ? entityType : "payment",
              entityId,
              null);
      case "who_else_can_act" -> {
        if (entityId == null) {
          yield null;
        }
        yield new MeIntent(
            kind,
            action != null ? action : "APPROVE",
            entityType != null ? entityType : "payment",
            entityId,
            null);
      }
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

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
