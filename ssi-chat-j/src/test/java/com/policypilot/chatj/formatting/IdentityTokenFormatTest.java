package com.policypilot.chatj.formatting;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class IdentityTokenFormatTest {

  private final IdentityTokenFormat format = new IdentityTokenFormat();

  @Test
  void wrapsScreamingSnakeTokens() {
    assertEquals("`INSTRUCTION_APPROVER`", format.formatToken("INSTRUCTION_APPROVER"));
    assertEquals("`MIDDLE_OFFICE`", format.formatToken("MIDDLE_OFFICE"));
  }

  @Test
  void leavesAlreadyBackticked() {
    assertEquals("`PAYMENT_CREATOR`", format.formatToken("`PAYMENT_CREATOR`"));
  }

  @Test
  void wrapsTokensInProseWithoutDoubleWrapping() {
    String text =
        "Someone with the INSTRUCTION_APPROVER role — see also `FUNDING_APPROVER` already wrapped.";
    String out = format.formatTokensInText(text);
    assertEquals(
        "Someone with the `INSTRUCTION_APPROVER` role — see also `FUNDING_APPROVER` already wrapped.",
        out);
  }

  @Test
  void formatTokenListJoinsWithBackticks() {
    assertEquals(
        "`PAYMENT_CREATOR`, `FUNDING_APPROVER`",
        format.formatTokenList(java.util.List.of("PAYMENT_CREATOR", "FUNDING_APPROVER")));
    assertEquals("—", format.formatTokenList(java.util.List.of()));
  }
}
