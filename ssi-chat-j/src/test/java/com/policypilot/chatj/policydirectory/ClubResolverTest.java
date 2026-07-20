package com.policypilot.chatj.policydirectory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ClubResolverTest {

  private static final Map<String, Double> LIMITS =
      Map.of(
          "UP_TO_100_MILLION_CLUB",
          100_000_000.0,
          "UP_TO_1_BILLION_CLUB",
          1_000_000_000.0,
          "UP_TO_100_BILLION_CLUB",
          100_000_000_000.0);
  private static final double ABSOLUTE = 100_000_000_000.0;

  @Test
  void llmSlotsDriveTwentyFiveBillionStrict() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who has permission to approve payments worth more than $25 billion?",
            25_000_000_000.0,
            true,
            LIMITS,
            ABSOLUTE);
    assertEquals(List.of("UP_TO_100_BILLION_CLUB"), resolution.clubs());
    assertEquals(25_000_000_000.0, resolution.amount());
    assertTrue(resolution.strict());
  }

  @Test
  void llmSlotsHandleWordedBillionInclusive() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who can approve a billion dollar payment?",
            1_000_000_000.0,
            false,
            LIMITS,
            ABSOLUTE);
    assertEquals(
        List.of("UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"), resolution.clubs());
    assertFalse(resolution.strict());
  }

  @Test
  void llmSlotsHandleOneBillionPayment() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who can approve one billion payment?", 1_000_000_000.0, false, LIMITS, ABSOLUTE);
    assertEquals(
        List.of("UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"), resolution.clubs());
  }

  @Test
  void omittingLlmAmountYieldsNoClubsEvenWithDollarPhrase() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who has permission to approve payments exceeding $1 million?",
            null,
            null,
            LIMITS,
            ABSOLUTE);
    assertTrue(resolution.clubs().isEmpty());
  }

  @Test
  void wordedBillionWithoutLlmSlotsYieldsNoClubs() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who can approve a billion dollar payment?", null, null, LIMITS, ABSOLUTE);
    assertTrue(resolution.clubs().isEmpty());
  }

  @Test
  void explicitClubNameWins() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve("List UP_TO_1_BILLION_CLUB members", null, null, LIMITS, ABSOLUTE);
    assertEquals(List.of("UP_TO_1_BILLION_CLUB"), resolution.clubs());
  }

  @Test
  void clubsForAmountInclusiveAtOneBillion() {
    assertEquals(
        List.of("UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"),
        ClubResolver.clubsForAmount(1_000_000_000.0, LIMITS, ABSOLUTE, false));
  }

  @Test
  void nullStrictDefaultsToTrueWhenAmountPresent() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve("amount question", 1_000_000_000.0, null, LIMITS, ABSOLUTE);
    assertTrue(resolution.strict());
    assertEquals(List.of("UP_TO_100_BILLION_CLUB"), resolution.clubs());
  }
}
