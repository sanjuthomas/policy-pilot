package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.skill.SkillSlots.CreateParams;
import java.time.LocalDate;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class SkillSlotsTest {

  @Test
  void resolveCreateUsesLlmSlots() {
    RouterDecision decision = new RouterDecision();
    decision.setSkillInstructionId("20260720-FICC-I-1");
    decision.setSkillAmount(1_000_000d);
    decision.setSkillValueDate("tomorrow");

    Optional<CreateParams> params = SkillSlots.resolveCreate(decision, "ignored free text");

    assertTrue(params.isPresent());
    assertEquals("20260720-FICC-I-1", params.get().instructionId());
    assertEquals(1_000_000d, params.get().amount());
    assertEquals(LocalDate.now().plusDays(1).toString(), params.get().valueDate());
  }

  @Test
  void resolveCreateAcceptsIsoValueDate() {
    RouterDecision decision = new RouterDecision();
    decision.setSkillInstructionId("20260720-FICC-I-1");
    decision.setSkillAmount(2.5e9);
    decision.setSkillValueDate("2026-08-01");

    Optional<CreateParams> params = SkillSlots.resolveCreate(decision, "");

    assertTrue(params.isPresent());
    assertEquals(2.5e9, params.get().amount());
    assertEquals("2026-08-01", params.get().valueDate());
  }

  @Test
  void resolveCreateFallsBackToInstructionIdInMessage() {
    RouterDecision decision = new RouterDecision();
    decision.setSkillAmount(1000d);
    decision.setSkillValueDate("today");

    Optional<CreateParams> params =
        SkillSlots.resolveCreate(
            decision, "create for instruction 20260720-FICC-I-2 amount irrelevant");

    assertTrue(params.isPresent());
    assertEquals("20260720-FICC-I-2", params.get().instructionId());
    assertEquals(LocalDate.now().toString(), params.get().valueDate());
  }

  @Test
  void resolveCreateEmptyWithoutAmountOrDateSlots() {
    RouterDecision decision = new RouterDecision();
    decision.setSkillInstructionId("20260720-FICC-I-1");
    assertTrue(SkillSlots.resolveCreate(decision, "").isEmpty());

    decision.setSkillAmount(1_000_000d);
    assertTrue(SkillSlots.resolveCreate(decision, "").isEmpty());
  }

  @Test
  void resolvePaymentIdPrefersLlmSlotThenMessage() {
    RouterDecision decision = new RouterDecision();
    decision.setSkillPaymentId("20260720-FICC-P-9");
    assertEquals(
        Optional.of("20260720-FICC-P-9"), SkillSlots.resolvePaymentId(decision, "no id here"));

    RouterDecision empty = new RouterDecision();
    assertEquals(
        Optional.of("20260720-FICC-P-8"),
        SkillSlots.resolvePaymentId(empty, "Please submit payment 20260720-FICC-P-8"));
    assertTrue(SkillSlots.resolvePaymentId(empty, "please submit the payment").isEmpty());
  }

  @Test
  void resolveValueDateRejectsGarbage() {
    assertEquals(null, SkillSlots.resolveValueDate(null));
    assertEquals(null, SkillSlots.resolveValueDate("next week"));
  }
}
