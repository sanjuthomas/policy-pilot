package com.policypilot.chatj.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Optional;
import org.junit.jupiter.api.Test;

class PaymentIdParserTest {

  @Test
  void extractsPaymentIdSlot() {
    assertEquals(
        Optional.of("PAY-abc123"),
        PaymentIdParser.extract("Who can approve payment PAY-abc123?"));
    assertEquals(Optional.empty(), PaymentIdParser.extract("Who am I?"));
  }
}
