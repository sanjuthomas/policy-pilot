package com.sanjuthomas.policypilot.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Optional;
import org.junit.jupiter.api.Test;

class PaymentIdParserTest {

  @Test
  void extractsSequencePaymentIdWithoutPaymentNoun() {
    assertEquals(
        Optional.of("20260720-FICC-P-8"),
        PaymentIdParser.extract("Who can approve 20260720-FICC-P-8?"));
  }

  @Test
  void extractsSequencePaymentIdWithPaymentNoun() {
    assertEquals(
        Optional.of("20260720-FICC-P-8"),
        PaymentIdParser.extract("Who can approve payment 20260720-FICC-P-8?"));
  }

  @Test
  void ignoresInstructionSequenceIds() {
    assertEquals(
        Optional.empty(), PaymentIdParser.extract("Who can approve 20260720-FICC-I-8?"));
  }

  @Test
  void ignoresLegacyPaymentTokens() {
    assertEquals(
        Optional.empty(), PaymentIdParser.extract("Who can approve payment PAY-abc123?"));
    assertEquals(Optional.empty(), PaymentIdParser.extract("Who am I?"));
  }

  @Test
  void doesNotTreatPaymentAndAsId() {
    assertEquals(
        Optional.empty(),
        PaymentIdParser.extract("Find reciprocal approval between payment and instruction"));
  }

  @Test
  void repairsSevenDigitDateTypo() {
    assertEquals(
        Optional.of("20260704-FICC-P-1"),
        PaymentIdParser.extract("approve 0260704-FICC-P-1"));
  }
}
