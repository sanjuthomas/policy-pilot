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

  @Test
  void doesNotTreatInstructionAndAsId() {
    assertEquals(
        Optional.empty(),
        InstructionIdParser.extract(
            "Are there any mutual approval cases (A approved B's instruction and B approved A's)?"));
  }

  @Test
  void ignoresLegacyUuidIds() {
    assertEquals(
        Optional.empty(),
        InstructionIdParser.extract(
            "Show instruction a1b2c3d4-e5f6-7890-abcd-ef1234567890"));
  }
}
