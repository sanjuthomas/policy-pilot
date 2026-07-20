package com.policypilot.chatj.formatting;

import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/** Humanize OPA allow_basis points for markdown tables — called from Thymeleaf. */
@Component
public class PolicyBasisFormat {

  private static final Pattern AMOUNT_IN_BASIS =
      Pattern.compile("(?i)amount\\s+([\\d.eE+-]+)\\s+(within subject and absolute limits)");

  public String humanizePoint(String point) {
    if (point == null || point.isBlank()) {
      return point;
    }
    Matcher matcher = AMOUNT_IN_BASIS.matcher(point);
    StringBuffer out = new StringBuffer();
    while (matcher.find()) {
      try {
        double amount = Double.parseDouble(matcher.group(1));
        String replacement = "amount " + formatUsdCompact(amount) + " " + matcher.group(2);
        matcher.appendReplacement(out, Matcher.quoteReplacement(replacement));
      } catch (NumberFormatException ex) {
        matcher.appendReplacement(out, Matcher.quoteReplacement(matcher.group(0)));
      }
    }
    matcher.appendTail(out);
    return out.toString();
  }

  static String formatUsdCompact(double amount) {
    double abs = Math.abs(amount);
    if (abs >= 1_000_000_000d) {
      double value = abs / 1_000_000_000d;
      if (value == Math.rint(value)) {
        return "$" + ((long) value) + " billion";
      }
      return "$" + trimOneDecimal(value) + " billion";
    }
    if (abs >= 1_000_000d) {
      double value = abs / 1_000_000d;
      if (value == Math.rint(value)) {
        return "$" + ((long) value) + " million";
      }
      return "$" + trimOneDecimal(value) + " million";
    }
    if (abs >= 1_000d) {
      return String.format("$%,.0f", abs);
    }
    if (abs == Math.rint(abs)) {
      return "$" + ((long) abs);
    }
    return String.format("$%.2f", abs);
  }

  private static String trimOneDecimal(double value) {
    String text = String.format("%.1f", value);
    if (text.endsWith(".0")) {
      return text.substring(0, text.length() - 2);
    }
    return text;
  }
}
