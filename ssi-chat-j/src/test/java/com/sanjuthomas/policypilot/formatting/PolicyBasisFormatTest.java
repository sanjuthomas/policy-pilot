package com.sanjuthomas.policypilot.formatting;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
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

  @Test
  void formatApprovalAuthLinesWhyOnlyWhenRedundant() {
    String summary =
        "Vasquez was allowed to APPROVE because role FICC_SUPERVISOR; valid transition";
    List<String> lines =
        basis.formatApprovalAuthLines(summary, List.of("role FICC_SUPERVISOR"));
    assertEquals(1, lines.size());
    assertTrue(lines.get(0).startsWith("WHY:"));
  }

  @Test
  void formatApprovalAuthLinesBasisWhenNoSummary() {
    List<String> lines =
        basis.formatApprovalAuthLines(
            null, List.of("amount 1000000 within subject and absolute limits", "role FUNDING_APPROVER"));
    assertEquals(1, lines.size());
    assertTrue(lines.get(0).startsWith("BASIS:"));
    assertTrue(lines.get(0).contains("$1 million"));
  }
}
