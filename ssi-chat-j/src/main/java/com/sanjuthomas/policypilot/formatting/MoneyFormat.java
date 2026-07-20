package com.sanjuthomas.policypilot.formatting;

import java.text.NumberFormat;
import java.util.Locale;
import org.springframework.stereotype.Component;

/** Display helper for monetary amounts — called from Thymeleaf answer templates. */
@Component
public class MoneyFormat {

  /**
   * Formats an amount with currency for prose, matching Python {@code format_money_amount}
   * (currency first with thousands separators), e.g. {@code USD 12,000,000.00}.
   */
  public String format(Object amount, String currency) {
    if (amount == null) {
      return "N/A";
    }
    String cur = currency == null || currency.isBlank() ? "" : currency.trim();
    try {
      double value =
          amount instanceof Number n ? n.doubleValue() : Double.parseDouble(String.valueOf(amount));
      NumberFormat nf = NumberFormat.getNumberInstance(Locale.US);
      nf.setMinimumFractionDigits(2);
      nf.setMaximumFractionDigits(2);
      String formatted = nf.format(value);
      if (cur.isEmpty()) {
        return formatted;
      }
      return cur + " " + formatted;
    } catch (NumberFormatException ex) {
      return cur.isEmpty() ? String.valueOf(amount) : amount + " " + cur;
    }
  }

  /**
   * Compact USD prose matching Python {@code format_usd_compact}, e.g. {@code $25 billion}.
   */
  public String formatUsdCompact(Object amount) {
    if (amount == null) {
      return "N/A";
    }
    double value;
    try {
      value =
          amount instanceof Number n ? n.doubleValue() : Double.parseDouble(String.valueOf(amount));
    } catch (NumberFormatException ex) {
      return String.valueOf(amount);
    }
    double abs = Math.abs(value);
    if (abs >= 1_000_000_000d) {
      double scaled = abs / 1_000_000_000d;
      if (scaled == Math.rint(scaled)) {
        return "$" + NumberFormat.getIntegerInstance(Locale.US).format((long) scaled) + " billion";
      }
      return "$" + trimTrailingZeros(scaled) + " billion";
    }
    if (abs >= 1_000_000d) {
      double scaled = abs / 1_000_000d;
      if (scaled == Math.rint(scaled)) {
        return "$" + NumberFormat.getIntegerInstance(Locale.US).format((long) scaled) + " million";
      }
      return "$" + trimTrailingZeros(scaled) + " million";
    }
    if (abs >= 1_000d) {
      NumberFormat nf = NumberFormat.getNumberInstance(Locale.US);
      nf.setMaximumFractionDigits(0);
      return "$" + nf.format(abs);
    }
    if (abs == Math.rint(abs)) {
      return "$" + ((long) abs);
    }
    NumberFormat nf = NumberFormat.getNumberInstance(Locale.US);
    nf.setMinimumFractionDigits(2);
    nf.setMaximumFractionDigits(2);
    return "$" + nf.format(abs);
  }

  private static String trimTrailingZeros(double scaled) {
    String s = String.format(Locale.US, "%.1f", scaled);
    if (s.endsWith(".0")) {
      return s.substring(0, s.length() - 2);
    }
    return s.replaceAll("0+$", "").replaceAll("\\.$", "");
  }
}
