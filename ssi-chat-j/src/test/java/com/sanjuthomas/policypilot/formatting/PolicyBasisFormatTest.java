package com.sanjuthomas.policypilot.formatting;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class PolicyBasisFormatTest {

  private final PolicyBasisFormat basis = new PolicyBasisFormat();

  @Test
  void humanizesScientificAmountInBasis() {
    assertEquals(
        "amount $12 million within subject and absolute limits; role FUNDING_APPROVER",
        basis.humanizePoint(
            "amount 1.2e+07 within subject and absolute limits; role FUNDING_APPROVER"));
  }

  @Test
  void leavesUnrelatedTextAlone() {
    assertEquals("covers LOB FICC", basis.humanizePoint("covers LOB FICC"));
  }
}
