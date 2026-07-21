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
    formatter =
        new Neo4jDirectAnswerFormatter(
            new AnswerRenderer(
                new AnswerTemplateConfig().answerTemplateEngine(),
                new MoneyFormat(),
                new PolicyBasisFormat()));
  }

  @Test
  void formatsPluralAlertCountToday() {
    String answer =
        formatter.format(
            "How many ALERT events happened today?",
            Set.of("count", "details"),
            List.of(Map.of("total", 5)));
    assertEquals("There were 5 ALERT events today.", answer);
  }

  @Test
  void formatsSingularAndZero() {
    assertTrue(
        formatter
            .format(
                "How many ALERT events happened today?",
                Set.of("count"),
                List.of(Map.of("total", 1)))
            .contains("1 ALERT event"));
    assertTrue(
        formatter
            .format("How many ALERT events happened today?", Set.of("count"), List.of())
            .contains("no ALERT events"));
  }

  @Test
  void formatsInstructionDenialWeek() {
    String answer =
        formatter.format(
            "How many instruction policy denials happened this week?",
            Set.of("count"),
            List.of(Map.of("total", 4)));
    assertEquals("There were 4 instruction policy denial events this week.", answer);
  }

  @Test
  void formatsPaymentDenialToday() {
    String answer =
        formatter.format(
            "How many payment policy denial alerts happened today?",
            Set.of("count"),
            List.of(Map.of("total", 3)));
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
                    "VIEW")));
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
                    0)));
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
  void formatsPaymentStatusMissing() {
    String answer =
        formatter.format(
            "What is the status of payment 20260720-FICC-P-9?",
            Set.of("payment_detail"),
            List.of(),
            "payment.status_by_id");
    assertEquals("No payment with that ID was found in the graph.", answer);
  }
}
