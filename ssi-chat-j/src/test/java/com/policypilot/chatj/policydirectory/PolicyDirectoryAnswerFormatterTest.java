package com.policypilot.chatj.policydirectory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.AnswerTemplateConfig;
import com.policypilot.chatj.formatting.MoneyFormat;
import com.policypilot.chatj.formatting.PolicyBasisFormat;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PolicyDirectoryAnswerFormatterTest {

  private final PolicyDirectoryAnswerFormatter formatter =
      new PolicyDirectoryAnswerFormatter(
          new AnswerRenderer(
              new AnswerTemplateConfig().answerTemplateEngine(),
              new MoneyFormat(),
              new PolicyBasisFormat()));

  @Test
  void formatsAmountClubHeaderAndTable() {
    String text =
        formatter.format(
            List.of("UP_TO_100_BILLION_CLUB"),
            25_000_000_000.0,
            true,
            null,
            List.of(
                Map.of(
                    "user_id",
                    "pay-204",
                    "display_name",
                    "Chen, Wei",
                    "title",
                    "Managing Director",
                    "groups",
                    List.of("MIDDLE_OFFICE", "UP_TO_100_BILLION_CLUB"),
                    "covering_lobs",
                    List.of("FICC", "FX"))));
    assertTrue(text.contains("exceeding $25 billion"));
    assertTrue(text.contains("UP_TO_100_BILLION_CLUB"));
    assertTrue(text.contains("pay-204"));
    assertTrue(text.contains("Covering LOBs"));
    assertTrue(text.contains("Groups"));
  }

  @Test
  void formatsEmptyMembers() {
    String text =
        formatter.format(List.of("UP_TO_100_BILLION_CLUB"), 25_000_000_000.0, true, null, List.of());
    assertTrue(text.contains("No matching users were found."));
  }

  @Test
  void multiClubHeaderListsClubs() {
    String text =
        formatter.format(
            List.of(
                "UP_TO_100_MILLION_CLUB", "UP_TO_1_BILLION_CLUB", "UP_TO_100_BILLION_CLUB"),
            1_000_000.0,
            true,
            null,
            List.of());
    assertTrue(text.contains("exceeding $1 million"));
    assertTrue(text.contains("UP_TO_100_MILLION_CLUB"));
  }

  @Test
  void coveringLobHeaderUsesPolicyDirectoryPhrase() {
    String text =
        formatter.format(
            List.of("MIDDLE_OFFICE"),
            null,
            true,
            "FICC",
            List.of(
                Map.of(
                    "user_id",
                    "pay-201",
                    "display_name",
                    "Laurent, Sophie",
                    "title",
                    "Vice President",
                    "groups",
                    List.of("MIDDLE_OFFICE"),
                    "covering_lobs",
                    List.of("FICC"))));
    assertTrue(text.contains("policy directory"));
    assertTrue(text.contains("FUNDING_APPROVER covering desk FICC"));
    assertEquals(true, text.contains("pay-201"));
  }
}
