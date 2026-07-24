package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ConfirmationCardTest {

  @Test
  void toApiIncludesPaymentFieldsWhenPresent() {
    ConfirmationCard card =
        new ConfirmationCard(
            "20260720-FICC-I-1",
            1_000_000d,
            "USD",
            "2026-07-21",
            "FICC",
            "APPROVED",
            "Acme Corp",
            "DE123",
            "Beta LLC",
            "998877",
            List.of("1. Big Bank"),
            "20260720-FICC-P-9",
            "DRAFT");

    Map<String, Object> api = card.toApi();
    assertEquals("20260720-FICC-I-1", api.get("instruction_id"));
    assertEquals("20260720-FICC-P-9", api.get("payment_id"));
    assertEquals("DRAFT", api.get("payment_status"));
    assertEquals(List.of("1. Big Bank"), api.get("intermediaries"));
  }

  @Test
  void toApiOmitsBlankPaymentFields() {
    ConfirmationCard card =
        new ConfirmationCard(
            "20260720-FICC-I-1",
            1_000_000d,
            "USD",
            "2026-07-21",
            "FICC",
            "APPROVED",
            null,
            null,
            null,
            null,
            null,
            null,
            null);

    Map<String, Object> api = card.toApi();
    assertFalse(api.containsKey("payment_id"));
    assertFalse(api.containsKey("payment_status"));
    assertTrue(((List<?>) api.get("intermediaries")).isEmpty());
  }
}
