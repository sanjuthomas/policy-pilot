package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.eligibility.EligibleApproversView.ApproverRow;
import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.MoneyFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

/** Maps eligibility API JSON to a view model and renders the answer template. */
@Component
public class EligibilityAnswerFormatter {

  private static final String TEMPLATE = "eligible-approvers";

  private final AnswerRenderer answerRenderer;

  public EligibilityAnswerFormatter(AnswerRenderer answerRenderer) {
    this.answerRenderer = answerRenderer;
  }

  public String formatEligibleApproversAnswer(Map<String, Object> data) {
    return answerRenderer.render(TEMPLATE, toView(data));
  }

  static EligibleApproversView toView(Map<String, Object> data) {
    String instructionId = str(data.get("instruction_id"));
    String instructionStatus = str(data.get("instruction_status"));
    String blocked = str(data.get("approval_blocked_reason"));
    List<Map<String, Object>> eligibleRaw = castListOfMaps(data.get("eligible"));
    List<ApproverRow> rows = new ArrayList<>();
    int index = 1;
    for (Map<String, Object> row : eligibleRaw) {
      rows.add(
          new ApproverRow(
              index++,
              firstNonBlank(str(row.get("display_name")), str(row.get("user_id")), "—"),
              firstNonBlank(str(row.get("title")), "—"),
              formatBasis(row.get("allow_basis"))));
    }
    Integer candidatesEvaluated = null;
    Object evaluated = data.get("candidates_evaluated");
    if (evaluated instanceof Number number) {
      candidatesEvaluated = number.intValue();
    } else if (evaluated != null && !str(evaluated).isBlank()) {
      try {
        candidatesEvaluated = Integer.parseInt(str(evaluated));
      } catch (NumberFormatException ignored) {
        // leave null
      }
    }
    return new EligibleApproversView(
        str(data.get("payment_id")),
        str(data.get("payment_status")),
        MoneyFormat.format(data.get("amount"), str(data.get("currency"))),
        str(data.get("owning_lob")),
        paymentInstructionSummary(instructionId, instructionStatus),
        blocked.isBlank() ? null : blocked,
        List.copyOf(rows),
        candidatesEvaluated);
  }

  private static String paymentInstructionSummary(String instructionId, String instructionStatus) {
    if (instructionId != null && !instructionId.isBlank()) {
      return "backing instruction " + instructionId + " (" + instructionStatus + ")";
    }
    return "instruction " + instructionStatus;
  }

  private static String formatBasis(Object allowBasis) {
    if (!(allowBasis instanceof List<?> list) || list.isEmpty()) {
      return "—";
    }
    return list.stream().map(String::valueOf).collect(Collectors.joining(", "));
  }

  @SuppressWarnings("unchecked")
  private static List<Map<String, Object>> castListOfMaps(Object value) {
    if (!(value instanceof List<?> list)) {
      return List.of();
    }
    return list.stream()
        .filter(Map.class::isInstance)
        .map(item -> (Map<String, Object>) item)
        .toList();
  }

  private static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }

  private static String firstNonBlank(String... values) {
    for (String value : values) {
      if (value != null && !value.isBlank()) {
        return value;
      }
    }
    return "";
  }
}
