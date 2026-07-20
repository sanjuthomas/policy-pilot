package com.policypilot.chatj.formatting;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class MoneyFormatTest {

  private final MoneyFormat money = new MoneyFormat();

  @Test
  void formatsWholeAndFractionalAmounts() {
    assertEquals("N/A", money.format(null, "USD"));
    assertEquals("USD 100.00", money.format(100, "USD"));
    assertEquals("USD 100,000,000.00", money.format(1.0E8, "USD"));
    assertEquals("EUR 12.34", money.format(12.34, "EUR"));
    assertEquals("12.00", money.format(12, ""));
  }
}
