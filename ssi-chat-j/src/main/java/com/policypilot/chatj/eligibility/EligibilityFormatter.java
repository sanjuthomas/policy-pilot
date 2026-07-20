package com.policypilot.chatj.eligibility;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public final class EligibilityFormatter {

  private EligibilityFormatter() {}

  @SuppressWarnings("unchecked")
  public static String formatEligibleApproversAnswer(Map<String, Object> data) {
    String paymentId = str(data.get("payment_id"));
    String status = str(data.get("payment_status"));
    String amountText = formatMoney(data.get("amount"), str(data.get("currency")));
    String owningLob = str(data.get("owning_lob"));
    String instructionId = str(data.get("instruction_id"));
    String instructionStatus = str(data.get("instruction_status"));
    String instructionSummary = paymentInstructionSummary(instructionId, instructionStatus);
    Object blocked = data.get("approval_blocked_reason");

    String header =
        "Live OPA evaluation for payment "
            + paymentId
            + " ("
            + status
            + ", "
            + amountText
            + ", desk "
            + owningLob
            + ", "
            + instructionSummary
            + ").";

    if (blocked != null && !str(blocked).isBlank()) {
      return header + "\n\n" + blocked;
    }

    List<Map<String, Object>> eligible = castListOfMaps(data.get("eligible"));
    if (eligible.isEmpty()) {
      return header + "\n\nNo users currently satisfy APPROVE for this payment.";
    }

    StringBuilder sb = new StringBuilder();
    sb.append(header).append("\n\nUsers who can approve this payment:\n\n");
    sb.append("| # | Approver | Title | Policy basis |\n");
    sb.append("|---|----------|-------|--------------|\n");
    int index = 1;
    for (Map<String, Object> row : eligible) {
      String name = firstNonBlank(str(row.get("display_name")), str(row.get("user_id")), "—");
      String title = firstNonBlank(str(row.get("title")), "—");
      String basis = formatBasis(row.get("allow_basis"));
      sb.append("| ")
          .append(index++)
          .append(" | ")
          .append(name)
          .append(" | ")
          .append(title)
          .append(" | ")
          .append(basis)
          .append(" |\n");
    }
    Object evaluated = data.get("candidates_evaluated");
    if (evaluated != null) {
      sb.append("\nEvaluated ")
          .append(evaluated)
          .append(" FUNDING_APPROVER candidate(s) from the user directory.");
    }
    return sb.toString().trim();
  }

  private static String paymentInstructionSummary(String instructionId, String instructionStatus) {
    if (instructionId != null && !instructionId.isBlank()) {
      return "backing instruction " + instructionId + " (" + instructionStatus + ")";
    }
    return "instruction " + instructionStatus;
  }

  private static String formatMoney(Object amount, String currency) {
    if (amount == null) {
      return "unknown amount";
    }
    String cur = currency == null || currency.isBlank() ? "USD" : currency;
    try {
      double value =
          amount instanceof Number n ? n.doubleValue() : Double.parseDouble(String.valueOf(amount));
      if (Math.abs(value) >= 1_000_000d) {
        return String.format(java.util.Locale.US, "%.0f %s", value, cur);
      }
      if (value == Math.rint(value)) {
        return String.format(java.util.Locale.US, "%.0f %s", value, cur);
      }
      return String.format(java.util.Locale.US, "%.2f %s", value, cur);
    } catch (NumberFormatException ex) {
      return amount + " " + cur;
    }
  }

  @SuppressWarnings("unchecked")
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
