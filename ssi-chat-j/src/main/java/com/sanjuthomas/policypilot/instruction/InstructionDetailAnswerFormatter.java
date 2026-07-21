package com.sanjuthomas.policypilot.instruction;

import com.sanjuthomas.policypilot.extraction.EntityUserDisplay;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/** Maps instruction-service GET JSON → Thymeleaf instruction detail card. */
@Component
public class InstructionDetailAnswerFormatter {

  private static final String TEMPLATE = "instruction-detail";

  private final AnswerRenderer answerRenderer;

  public InstructionDetailAnswerFormatter(AnswerRenderer answerRenderer) {
    this.answerRenderer = answerRenderer;
  }

  public String format(Map<String, Object> data) {
    return answerRenderer.render(TEMPLATE, toView(data));
  }

  static InstructionDetailAnswerView toView(Map<String, Object> data) {
    return new InstructionDetailAnswerView(
        dash(str(data.get("instruction_id"))),
        dash(str(data.get("status"))),
        dash(str(data.get("instruction_type"))),
        dash(str(data.get("owning_lob"))),
        dash(str(data.get("currency"))),
        dash(str(data.get("wire_scope"))),
        creditorDisplay(data.get("creditor"), data.get("creditor_account")),
        dash(str(data.get("effective_date"))),
        dash(str(data.get("end_date"))),
        versionCell(data.get("version_number")),
        EntityUserDisplay.creator(data.get("created_by")),
        EntityUserDisplay.approver(data.get("approved_by")),
        blankToNull(str(data.get("created_at"))),
        blankToNull(str(data.get("approved_at"))));
  }

  static String creditorDisplay(Object creditor, Object account) {
    String name = "—";
    if (creditor instanceof Map<?, ?> party) {
      String partyName = str(party.get("name")).strip();
      if (StringUtils.hasText(partyName) && !isNullish(partyName)) {
        name = partyName;
      }
    }
    String accountId = "";
    if (account instanceof Map<?, ?> cash) {
      String identification = str(cash.get("identification")).strip();
      if (StringUtils.hasText(identification) && !isNullish(identification)) {
        accountId = identification;
      }
    }
    if (StringUtils.hasText(accountId)) {
      return "—".equals(name) ? "`" + accountId + "`" : name + " (`" + accountId + "`)";
    }
    return name;
  }

  private static String versionCell(Object version) {
    if (version == null) {
      return "—";
    }
    String text = str(version).strip();
    return StringUtils.hasText(text) ? text : "—";
  }

  private static boolean isNullish(String value) {
    String lower = value.toLowerCase();
    return "none".equals(lower) || "null".equals(lower);
  }

  private static String dash(String value) {
    return StringUtils.hasText(value) ? value : "—";
  }

  private static String blankToNull(String value) {
    return StringUtils.hasText(value) ? value : null;
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }
}
