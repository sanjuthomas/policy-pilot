package com.policypilot.chatj.formatting;

import java.util.Locale;

/** Shared display helpers for monetary amounts in chat answers. */
public final class MoneyFormat {

  private MoneyFormat() {}

  /**
   * Formats an amount with currency for prose (e.g. {@code 100 USD}, {@code 100000000 USD}).
   * Returns {@code unknown amount} when {@code amount} is null.
   */
  public static String format(Object amount, String currency) {
    if (amount == null) {
      return "unknown amount";
    }
    String cur = currency == null || currency.isBlank() ? "USD" : currency.trim();
    try {
      double value =
          amount instanceof Number n ? n.doubleValue() : Double.parseDouble(String.valueOf(amount));
      if (Math.abs(value) >= 1_000_000d) {
        return String.format(Locale.US, "%.0f %s", value, cur);
      }
      if (value == Math.rint(value)) {
        return String.format(Locale.US, "%.0f %s", value, cur);
      }
      return String.format(Locale.US, "%.2f %s", value, cur);
    } catch (NumberFormatException ex) {
      return amount + " " + cur;
    }
  }
}
