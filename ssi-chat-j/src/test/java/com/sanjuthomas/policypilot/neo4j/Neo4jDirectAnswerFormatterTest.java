package com.sanjuthomas.policypilot.neo4j;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class Neo4jDirectAnswerFormatterTest {

  private Neo4jDirectAnswerFormatter formatter;

  @BeforeEach
  void setUp() {
    PolicyBasisFormat basis = new PolicyBasisFormat();
    formatter =
        new Neo4jDirectAnswerFormatter(
            new AnswerRenderer(
                new AnswerTemplateConfig().answerTemplateEngine(),
                new MoneyFormat(),
                basis),
            basis);
  }

  @Test
  void formatsPluralAlertCountToday() {
    String answer =
        formatter.format(
            "How many ALERT events happened today?",
            Set.of("count", "details"),
            List.of(Map.of("total", 5)),
            null,
            new GraphAnswerHints("today", null, "alert"));
    assertEquals("There were 5 ALERT events today.", answer);
  }

  @Test
  void formatsSingularAndZero() {
    GraphAnswerHints hints = new GraphAnswerHints("today", null, "alert");
    assertTrue(
        formatter
            .format(
                "How many ALERT events happened today?",
                Set.of("count"),
                List.of(Map.of("total", 1)),
                null,
                hints)
            .contains("1 ALERT event"));
    assertTrue(
        formatter
            .format(
                "How many ALERT events happened today?",
                Set.of("count"),
                List.of(),
                null,
                hints)
            .contains("no ALERT events"));
  }

  @Test
  void formatsInstructionDenialWeek() {
    String answer =
        formatter.format(
            "How many instruction policy denials happened this week?",
            Set.of("count"),
            List.of(Map.of("total", 4)),
            null,
            new GraphAnswerHints("week", "instruction", "denial"));
    assertEquals("There were 4 instruction policy denial events this week.", answer);
  }

  @Test
  void formatsPaymentDenialToday() {
    String answer =
        formatter.format(
            "How many payment policy denial alerts happened today?",
            Set.of("count"),
            List.of(Map.of("total", 3)),
            null,
            new GraphAnswerHints("today", "payment", "denial"));
    assertEquals("There were 3 payment policy denial events today.", answer);
  }

  @Test
  void formatsAlertListWithEntityIds() {
    String answer =
        formatter.format(
            "Can you list all instruction denial events for this week?",
            Set.of("security_event_alert_list"),
            List.of(
                Map.of(
                    "event_id",
                    "e1",
                    "timestamp",
                    "t",
                    "entity_type",
                    "instruction",
                    "entity_id",
                    "20260720-FICC-I-1",
                    "actor_display",
                    "Ada",
                    "action",
                    "VIEW")),
            null,
            new GraphAnswerHints("week", "instruction", "denial"));
    assertTrue(answer.contains("ALERT security events (1)"));
    assertTrue(answer.contains("Entity ID"));
    assertTrue(answer.contains("20260720-FICC-I-1"));
  }

  @Test
  void formatsRanking() {
    String answer =
        formatter.format(
            "Which user triggered the most policy denial alerts this week?",
            Set.of("ranking"),
            List.of(
                Map.of(
                    "actor_display",
                    "Pay One",
                    "user_id",
                    "pay-101",
                    "alert_count",
                    2,
                    "payment_alerts",
                    2,
                    "instruction_alerts",
                    0)),
            null,
            new GraphAnswerHints("week", null, "denial"));
    assertTrue(answer.contains("pay-101"));
    assertTrue(answer.contains("most policy denial alerts"));
  }

  @Test
  void formatsPaymentStatusById() {
    String answer =
        formatter.format(
            "What is the status of payment 20260720-FICC-P-1?",
            Set.of("payment_detail"),
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-1",
                    "status",
                    "APPROVED",
                    "owning_lob",
                    "FICC")),
            "payment.status_by_id");
    assertEquals("Payment 20260720-FICC-P-1 has status APPROVED (LOB FICC).", answer);
  }

  @Test
  void formatsInstructionStatusById() {
    String answer =
        formatter.format(
            "What is the status of instruction 20260720-FICC-I-1?",
            Set.of("instruction_detail"),
            List.of(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "status",
                    "APPROVED",
                    "owning_lob",
                    "FICC")),
            "instruction.status_by_id");
    assertEquals("Instruction 20260720-FICC-I-1 has status APPROVED (LOB FICC).", answer);
  }

  @Test
  void formatsPaymentCreatorById() {
    String answer =
        formatter.format(
            "Who created payment 20260720-FICC-P-1?",
            Set.of("payment_detail"),
            List.of(
                Map.of(
                    "payment_id", "20260720-FICC-P-1", "creator_display", "Alice Ops")),
            "payment.creator_by_id");
    assertEquals("Payment 20260720-FICC-P-1 was created by Alice Ops.", answer);
  }

  @Test
  void formatsInstructionCreatorById() {
    String answer =
        formatter.format(
            "Who created instruction 20260720-FICC-I-1?",
            Set.of("instruction_detail"),
            List.of(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "creator_display",
                    "Okonkwo, David (mo-050)")),
            "instruction.creator_by_id");
    assertEquals(
        "Instruction 20260720-FICC-I-1 was created by Okonkwo, David (mo-050).", answer);
  }

  @Test
  void formatsPaymentCreatorAndApproverById() {
    String answer =
        formatter.format(
            "Who created payment 20260720-FICC-P-1 and who approved it?",
            Set.of("payment_detail"),
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-1",
                    "creator_display",
                    "Alice Ops",
                    "approver_display",
                    "Vasquez, Elena (ficc-300)",
                    "approved_at",
                    "2026-07-04T12:29:42")),
            "payment.creator_and_approver_by_id");
    assertTrue(answer.contains("Payment: 20260720-FICC-P-1"));
    assertTrue(answer.contains("Creator: Alice Ops"));
    assertTrue(answer.contains("Approver: Vasquez, Elena (ficc-300)"));
    assertTrue(answer.contains("Approved at: 2026-07-04T12:29:42"));
  }

  @Test
  void formatsInstructionCreatorAndApproverById() {
    String answer =
        formatter.format(
            "Who created instruction 20260720-FICC-I-1 and who approved it?",
            Set.of("instruction_detail"),
            List.of(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "creator_display",
                    "Okonkwo, David (mo-050)",
                    "approver_display",
                    "Nguyen, Caroline (ficc-500)")),
            "instruction.creator_and_approver_by_id");
    assertTrue(answer.contains("Instruction: 20260720-FICC-I-1"));
    assertTrue(answer.contains("Creator: Okonkwo, David (mo-050)"));
    assertTrue(answer.contains("Approver: Nguyen, Caroline (ficc-500)"));
  }

  @Test
  void formatsInstructionInventoryTable() {
    String answer =
        formatter.format(
            "Can you list all approved instructions?",
            Set.of("instruction_inventory"),
            List.of(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "status",
                    "APPROVED",
                    "owning_lob",
                    "FICC",
                    "currency",
                    "USD",
                    "creator_display",
                    "Okonkwo, David (mo-050)",
                    "approver_display",
                    "Nguyen, Caroline (ficc-500)")),
            "instruction.list_by_status");
    assertTrue(answer.contains("Found 1 instruction(s)."));
    assertTrue(answer.contains("Instruction ID"));
    assertTrue(answer.contains("20260720-FICC-I-1"));
    assertTrue(answer.contains("APPROVED"));
    assertTrue(answer.contains("Okonkwo, David (mo-050)"));
  }

  @Test
  void formatsInstructionInventoryEmpty() {
    String answer =
        formatter.format(
            "Can you list all approved instructions?",
            Set.of("instruction_inventory"),
            List.of(),
            "instruction.list_by_status");
    assertEquals("No matching instructions were found in the graph.", answer);
  }

  @Test
  void formatsPaymentStatusMissing() {
    String answer =
        formatter.format(
            "What is the status of payment 20260720-FICC-P-9?",
            Set.of("payment_detail"),
            List.of(),
            "payment.status_by_id");
    assertEquals("No payment with that ID was found in the graph.", answer);
  }

  @Test
  void formatsPaymentApprovalLookupWithWhy() {
    String answer =
        formatter.format(
            "Who approved payment 20260720-FICC-P-1 and why?",
            Set.of("payment_approval_lookup"),
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-1",
                    "approver_display",
                    "Vasquez, Elena (ficc-300)",
                    "approved_at",
                    "2026-07-04T12:29:42",
                    "authorization_summary",
                    "Vasquez was allowed to APPROVE because role FICC_SUPERVISOR",
                    "authorization_basis",
                    List.of("role FICC_SUPERVISOR"))),
            "planned_graph");
    assertTrue(answer.contains("Payment: 20260720-FICC-P-1"));
    assertTrue(answer.contains("WHO: Vasquez, Elena (ficc-300)"));
    assertTrue(answer.contains("WHEN: 2026-07-04T12:29:42"));
    assertTrue(answer.contains("BASIS:"));
    assertTrue(answer.contains("FICC_SUPERVISOR"));
    assertTrue(!answer.contains("WHY:"));
  }

  @Test
  void formatsPaymentApprovalLookupMissing() {
    String answer =
        formatter.format(
            "Who approved payment 20260720-FICC-P-9 and why?",
            Set.of("payment_approval_lookup"),
            List.of(),
            "planned_graph");
    assertEquals("No payment with that ID was found.", answer);
  }

  @Test
  void formatsPaymentApprovalLookupNotApprovedWithStatus() {
    String answer =
        formatter.format(
            "Who approved 20260720-FICC-P-19?",
            Set.of("payment_approval_lookup"),
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-19",
                    "status",
                    "CANCELLED",
                    "has_approval",
                    false,
                    "approver_display",
                    "")),
            "payment.approver_by_id");
    assertEquals(
        "Payment 20260720-FICC-P-19 was not approved. Its status is CANCELLED.", answer);
  }

  @Test
  void formatsPaymentApprovalLookupWhenHasApprovalFalseButApproverPresent() {
    String answer =
        formatter.format(
            "Who approved payment 20260720-FICC-P-1 and why?",
            Set.of("payment_approval_lookup"),
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-1",
                    "status",
                    "APPROVED",
                    "has_approval",
                    false,
                    "approver_display",
                    "Laurent, Sophie (pay-201)",
                    "approved_at",
                    "2026-07-20T01:19:04.508813Z",
                    "authorization_summary",
                    "Laurent, Sophie (pay-201) was allowed to APPROVE because role FUNDING_APPROVER")),
            "planned_graph");
    assertTrue(answer.contains("Payment: 20260720-FICC-P-1"));
    assertTrue(answer.contains("WHO: Laurent, Sophie (pay-201)"));
    assertTrue(answer.contains("WHEN: 2026-07-20T01:19:04.508813Z"));
    assertTrue(answer.contains("BASIS:"));
    assertTrue(answer.contains("FUNDING_APPROVER"));
    assertTrue(!answer.contains("WHY:"));
    assertTrue(!answer.contains("was not approved"));
  }

  @Test
  void formatsSelfApprovalComplianceTable() {
    String answer =
        formatter.format(
            "Show self-approved instructions",
            Set.of("self_approval"),
            List.of(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "owning_lob",
                    "FICC",
                    "status",
                    "APPROVED",
                    "creator_display",
                    "Ada")),
            "instruction.self_approval");
    assertTrue(answer.contains("Found 1 matching instruction(s)."));
    assertTrue(answer.contains("20260720-FICC-I-1"));
    assertTrue(answer.contains("Ada"));
  }

  @Test
  void formatsMutualApprovalEmpty() {
    String answer =
        formatter.format(
            "mutual approval",
            Set.of("mutual_approval"),
            List.of(),
            "instruction.mutual_approval");
    assertEquals("No mutual approval cases were found in the graph.", answer);
  }
}
