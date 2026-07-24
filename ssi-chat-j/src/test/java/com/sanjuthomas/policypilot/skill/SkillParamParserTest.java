package com.sanjuthomas.policypilot.skill;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.skill.SkillParamParser.CreateParams;
import java.time.LocalDate;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class SkillParamParserTest {

  @Test
  void parseCreateExtractsInstructionAmountMillionAndTomorrow() {
    Optional<CreateParams> params =
        SkillParamParser.parseCreate(
            "Can you create a payment for instruction ID 20260720-FICC-I-1? "
                + "Value date tomorrow; amount: 1 million USD.");

    assertTrue(params.isPresent());
    assertEquals("20260720-FICC-I-1", params.get().instructionId());
    assertEquals(1_000_000d, params.get().amount());
    assertEquals(LocalDate.now().plusDays(1).toString(), params.get().valueDate());
  }

  @Test
  void parseCreateParsesIsoValueDateAndBillionSuffix() {
    Optional<CreateParams> params =
        SkillParamParser.parseCreate(
            "Please create a payment for instruction 20260720-FICC-I-2 amount 2b value date "
                + "2026-08-01");

    assertTrue(params.isPresent());
    assertEquals(2_000_000_000d, params.get().amount());
    assertEquals("2026-08-01", params.get().valueDate());
  }

  @Test
  void parseCreateReturnsEmptyWhenSlotsMissing() {
    assertTrue(SkillParamParser.parseCreate("please create a payment").isEmpty());
    assertTrue(
        SkillParamParser.parseCreate("create for instruction 20260720-FICC-I-1").isEmpty());
    assertTrue(SkillParamParser.parseCreate("").isEmpty());
    assertTrue(SkillParamParser.parseCreate(null).isEmpty());
  }

  @Test
  void parseAmountHandlesThousandAndBareNumber() {
    assertEquals(25_000d, SkillParamParser.parseAmount("amount 25k"));
    assertEquals(1_500_000d, SkillParamParser.parseAmount("for $1,500,000"));
  }

  @Test
  void parsePaymentIdExtractsSequenceId() {
    assertEquals(
        Optional.of("20260720-FICC-P-9"),
        SkillParamParser.parsePaymentId("Please submit payment 20260720-FICC-P-9 for approval."));
    assertTrue(SkillParamParser.parsePaymentId("please submit the payment").isEmpty());
  }
}
