package com.policypilot.chatj.me;

/**
 * Resolved me-intent slots (path is law: {@code path=me} + {@code meKind}).
 *
 * <p>Parity with Python {@code MeIntent}.
 */
public record MeIntent(
    String kind,
    String action,
    String entityType,
    String entityId,
    String coveringLob) {

  public static MeIntent ofKind(String kind) {
    return new MeIntent(kind, null, null, null, null);
  }
}
