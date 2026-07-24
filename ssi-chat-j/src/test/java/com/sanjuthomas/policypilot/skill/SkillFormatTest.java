package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.auth.Subject;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class SkillFormatTest {

  private static Map<String, Object> instruction() {
    return Map.of(
        "instruction_id", "20260720-FICC-I-1",
        "currency", "USD",
        "owning_lob", "FICC",
        "status", "APPROVED",
        "debtor", Map.of("name", "Acme Corp"),
        "debtor_account", Map.of("identification_scheme", "IBAN", "identification", "DE123"),
        "creditor", Map.of("name", "Beta LLC"),
        "creditor_account", Map.of("identification", "998877"),
        "intermediary_agents",
            List.of(
                Map.of(
                    "agent",
                        Map.of(
                            "financial_institution",
                            Map.of("name", "Big Bank", "identification", "BIGBUS33")),
                    "account", Map.of("identification", "INT-1"))));
  }

  @Test
  void formatAmountUsesNoDecimalsForWholeMillions() {
    assertEquals("USD 1,000,000", SkillFormat.formatAmount(1_000_000d, "USD"));
    assertEquals("USD 1,234.56", SkillFormat.formatAmount(1_234.56d, "USD"));
    assertEquals("USD 500.00", SkillFormat.formatAmount(500d, null));
  }

  @Test
  void cardFromInstructionMapsPartiesAccountsAndIntermediaries() {
    ConfirmationCard card =
        SkillFormat.cardFromInstruction(instruction(), 1_000_000d, "2026-07-21", "20260720-FICC-P-9", "DRAFT");
    assertEquals("20260720-FICC-I-1", card.instructionId());
    assertEquals("Acme Corp", card.debtorName());
    assertEquals("IBAN:DE123", card.debtorAccount());
    assertEquals("Beta LLC", card.creditorName());
    assertEquals("998877", card.creditorAccount());
    assertEquals(1, card.intermediaries().size());
    assertTrue(card.intermediaries().get(0).contains("Big Bank"));
    assertTrue(card.intermediaries().get(0).contains("BIGBUS33"));
  }

  @Test
  void reportsRenderTables() {
    ConfirmationCard card =
        SkillFormat.cardFromInstruction(instruction(), 1_000_000d, "2026-07-21", "20260720-FICC-P-9", "DRAFT");
    Map<String, Object> payment =
        Map.of(
            "payment_id", "20260720-FICC-P-9",
            "status", "DRAFT",
            "amount", 1_000_000,
            "currency", "USD",
            "owning_lob", "FICC");

    assertTrue(SkillFormat.createdReport(payment, card).contains("Payment created (DRAFT)"));
    assertTrue(SkillFormat.submittedReport(payment, card).contains("submitted for funding approval"));
    assertTrue(
        SkillFormat.approvedReport(payment, card, "Nguyen, Caroline").contains("Payment approved"));
    assertTrue(
        SkillFormat.cancelledReport(payment, card, "Chen, Sarah").contains("Payment cancelled"));
  }

  @Test
  void displayNamePrefersFamilyGiven() {
    Subject full =
        new Subject(
            "pay-101", "Emily", "Rodriguez", "Analyst", "FICC", List.of(), List.of(), null, List.of(), "t", "s");
    assertEquals("Rodriguez, Emily", SkillFormat.displayName(full));

    Subject sparse =
        new Subject("pay-102", "", "", "Analyst", "FICC", List.of(), List.of(), null, List.of(), "t", "s");
    assertEquals("pay-102", SkillFormat.displayName(sparse));
  }

  @Test
  void violationsAndBasisJoinOrFallBack() {
    assertEquals("policy did not allow the action", SkillFormat.violations(List.of()));
    assertEquals("a; b", SkillFormat.violations(List.of("a", "b")));
    assertEquals("CREATE allowed", SkillFormat.basis(List.of(), "CREATE allowed"));
    assertEquals("role PAYMENT_CREATOR", SkillFormat.basis(List.of("role PAYMENT_CREATOR"), "x"));
  }

  @Test
  void numericHelpersFallBack() {
    assertEquals(2, SkillFormat.asInt("2", 1));
    assertEquals(1, SkillFormat.asInt("nope", 1));
    assertEquals(3.5d, SkillFormat.asDouble("3.5", 0));
    assertEquals(9d, SkillFormat.asDouble(null, 9));
    assertEquals("", SkillFormat.str(null));
    assertEquals("FICC", SkillFormat.firstNonBlank("", "FICC"));
  }
}
