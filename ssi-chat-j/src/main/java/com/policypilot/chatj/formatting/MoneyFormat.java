package com.policypilot.chatj.formatting;

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
}
