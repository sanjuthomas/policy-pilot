package com.policypilot.chatj.formatting;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class MoneyFormatTest {

  @Test
  void formatsWholeAndFractionalAmounts() {
    assertEquals("unknown amount", MoneyFormat.format(null, "USD"));
    assertEquals("100 USD", MoneyFormat.format(100, "USD"));
    assertEquals("100000000 USD", MoneyFormat.format(1.0E8, "USD"));
    assertEquals("12.34 EUR", MoneyFormat.format(12.34, "EUR"));
  }
}
