package com.sanjuthomas.policypilot.extraction;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class EntityApiAnswerFormatterInventoryTest {

  private EntityApiAnswerFormatter formatter;

  @BeforeEach
  void setUp() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    formatter = new EntityApiAnswerFormatter(renderer, new PolicyBasisFormat());
  }

  @Test
  void formatsZeroAndPositiveCounts() {
    assertTrue(formatter.formatInventoryCount(0, "instructions").contains("Found 0 matching"));
    assertTrue(formatter.formatInventoryCount(3, "payments").contains("Found 3 matching payments"));
  }

  @Test
  void formatsGroupByStatusAndEmpty() {
    assertTrue(formatter.formatGroupByStatus(Map.of(), "Instructions").contains("No matching"));
    Map<String, Long> counts = new LinkedHashMap<>();
    counts.put("APPROVED", 2L);
    counts.put("SUBMITTED", 1L);
    String text = formatter.formatGroupByStatus(counts, "Instructions");
    assertTrue(text.contains("Instructions by status"));
    assertTrue(text.contains("APPROVED: 2"));
    assertTrue(text.contains("SUBMITTED: 1"));
  }

  @Test
  void formatsGroupByLob() {
    Map<String, Long> counts = new LinkedHashMap<>();
    counts.put("FICC", 3L);
    counts.put("FX", 1L);
    String text = formatter.formatGroupByLob(counts, "Instructions");
    assertTrue(text.contains("Instructions by LOB"));
    assertTrue(text.contains("FICC: 3"));
    assertTrue(text.contains("FX: 1"));
  }

  @Test
  void formatsPaymentInventoryTable() {
    String empty = formatter.formatPaymentInventory(List.of());
    assertTrue(empty.contains("No matching payments"));

    String table =
        formatter.formatPaymentInventory(
            List.of(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-1",
                    "status",
                    "SUBMITTED",
                    "owning_lob",
                    "FICC",
                    "currency",
                    "USD",
                    "created_by",
                    Map.of("user_id", "fo-100"))));
    assertTrue(table.contains("Found 1 payment"));
    assertTrue(table.contains("20260720-FICC-P-1"));
    assertTrue(table.contains("SUBMITTED"));
  }
}
