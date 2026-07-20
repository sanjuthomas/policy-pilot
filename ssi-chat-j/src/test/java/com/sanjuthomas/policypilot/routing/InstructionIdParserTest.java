package com.sanjuthomas.policypilot.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Optional;
import org.junit.jupiter.api.Test;

class InstructionIdParserTest {

  @Test
  void extractsSequenceInstructionIdWithoutNoun() {
    assertEquals(
        Optional.of("20260720-FICC-I-1"),
        InstructionIdParser.extract("Who can approve 20260720-FICC-I-1?"));
  }

  @Test
  void extractsSequenceInstructionIdWithNoun() {
    assertEquals(
        Optional.of("20260720-FICC-I-1"),
        InstructionIdParser.extract("Who can approve instruction 20260720-FICC-I-1?"));
  }

  @Test
  void ignoresPaymentSequenceIds() {
    assertEquals(
        Optional.empty(), InstructionIdParser.extract("Who can approve 20260720-FICC-P-8?"));
  }
}
