package com.policypilot.chatj.policydirectory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
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
            null,
            LIMITS,
            ABSOLUTE);
    assertEquals(List.of("UP_TO_100_BILLION_CLUB"), resolution.clubs());
    assertEquals(25_000_000_000.0, resolution.amount());
    assertTrue(resolution.strict());
    assertNull(resolution.coveringLob());
  }

  @Test
  void llmSlotsHandleWordedBillionInclusive() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who can approve a billion dollar payment?",
            1_000_000_000.0,
            false,
            null,
            LIMITS,
            ABSOLUTE);
    assertEquals(
        List.of("UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"), resolution.clubs());
    assertFalse(resolution.strict());
  }

  @Test
  void coveringLobOnlyUsesMiddleOffice() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Which users have permission to approve payments covering FICC?",
            null,
            null,
            "FICC",
            Map.of(),
            0);
    assertEquals(List.of(ClubResolver.FUNDING_APPROVER_ORG_GROUP), resolution.clubs());
    assertEquals("FICC", resolution.coveringLob());
    assertNull(resolution.amount());
  }

  @Test
  void coveringLobNormalizedToUpperCase() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve("covering ficc", null, null, "ficc", Map.of(), 0);
    assertEquals("FICC", resolution.coveringLob());
  }

  @Test
  void amountPlusCoveringLobKeepsBoth() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "exceeding $1 million for FICC",
            1_000_000.0,
            true,
            "FICC",
            LIMITS,
            ABSOLUTE);
    assertEquals(
        List.of(
            "UP_TO_100_MILLION_CLUB", "UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"),
        resolution.clubs());
    assertEquals("FICC", resolution.coveringLob());
  }

  @Test
  void omittingSlotsYieldsNoClubs() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "Who has permission to approve payments exceeding $1 million?",
            null,
            null,
            null,
            LIMITS,
            ABSOLUTE);
    assertTrue(resolution.clubs().isEmpty());
  }

  @Test
  void explicitClubNameWins() {
    ClubResolver.ClubResolution resolution =
        ClubResolver.resolve(
            "List UP_TO_1_BILLION_CLUB members", null, null, null, LIMITS, ABSOLUTE);
    assertEquals(List.of("UP_TO_1_BILLION_CLUB"), resolution.clubs());
  }

  @Test
  void clubsForAmountInclusiveAtOneBillion() {
    assertEquals(
        List.of("UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"),
        ClubResolver.clubsForAmount(1_000_000_000.0, LIMITS, ABSOLUTE, false));
  }
}
