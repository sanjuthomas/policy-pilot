package com.policypilot.chatj.routing;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Slot parsing only — not intent classification. */
public final class PaymentIdParser {

  private static final Pattern PAYMENT_ID =
      Pattern.compile("(?i)\\bpayment\\s+([A-Za-z0-9._:-]+)");

  private PaymentIdParser() {}

  public static Optional<String> extract(String question) {
    Matcher matcher = PAYMENT_ID.matcher(question == null ? "" : question);
    if (matcher.find()) {
      return Optional.of(matcher.group(1).replaceAll("[?.!,;:]+$", ""));
    }
    return Optional.empty();
  }
}
