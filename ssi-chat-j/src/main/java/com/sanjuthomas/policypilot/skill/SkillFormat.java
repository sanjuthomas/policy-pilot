package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.Subject;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Confirmation-card assembly and success-report markdown for payment mutation skills. Mirrors
 * Python {@code chat_application.skills.format}.
 */
public final class SkillFormat {

  private SkillFormat() {}

  public static ConfirmationCard cardFromInstruction(
      Map<String, Object> instruction,
      double amount,
      String valueDate,
      String paymentId,
      String paymentStatus) {
    return new ConfirmationCard(
        str(instruction.get("instruction_id")),
        amount,
        str(instruction.get("currency")),
        valueDate,
        str(instruction.get("owning_lob")),
        str(instruction.get("status")),
        partyName(instruction.get("debtor")),
        accountId(instruction.get("debtor_account")),
        partyName(instruction.get("creditor")),
        accountId(instruction.get("creditor_account")),
        intermediaryLines(instruction),
        paymentId,
        paymentStatus);
  }

  public static String formatAmount(double amount, String currency) {
    String cur = currency == null || currency.isBlank() ? "USD" : currency;
    if (amount >= 1_000_000d && amount == Math.floor(amount)) {
      return String.format(Locale.US, "%s %,.0f", cur, amount);
    }
    return String.format(Locale.US, "%s %,.2f", cur, amount);
  }

  public static String createdReport(Map<String, Object> payment, ConfirmationCard card) {
    String paymentId = firstNonBlank(str(payment.get("payment_id")), "—");
    List<String> lines = new ArrayList<>();
    lines.add("### Payment created (DRAFT)");
    lines.add("");
    lines.add("| Field | Value |");
    lines.add("| --- | --- |");
    lines.add("| Payment id | `" + paymentId + "` |");
    lines.add("| Instruction | `" + card.instructionId() + "` |");
    lines.add("| Value date | " + card.valueDate() + " |");
    lines.add("| Amount | " + reportAmount(payment, card) + " |");
    lines.add("| Owning LOB | **" + firstNonBlank(str(payment.get("owning_lob")), card.owningLob()) + "** |");
    lines.add("| Status | " + firstNonBlank(str(payment.get("status")), "DRAFT") + " |");
    lines.add("");
    lines.add(
        "An owning-LOB desk analyst (`fo-*`) with `PAYMENT_CREATOR` can submit this draft for "
            + "funding approval via chat.");
    lines.add("");
    return String.join("\n", lines);
  }

  public static String submittedReport(Map<String, Object> payment, ConfirmationCard card) {
    String paymentId = firstNonBlank(str(payment.get("payment_id")), card.paymentId(), "—");
    List<String> lines = new ArrayList<>();
    lines.add("### Payment submitted for funding approval");
    lines.add("");
    lines.add("| Field | Value |");
    lines.add("| --- | --- |");
    lines.add("| Payment id | `" + paymentId + "` |");
    lines.add("| Instruction | `" + card.instructionId() + "` |");
    lines.add("| Value date | " + card.valueDate() + " |");
    lines.add("| Amount | " + reportAmount(payment, card) + " |");
    lines.add("| Owning LOB | **" + firstNonBlank(str(payment.get("owning_lob")), card.owningLob()) + "** |");
    lines.add("| Status | " + firstNonBlank(str(payment.get("status")), "SUBMITTED") + " |");
    lines.add("");
    lines.add("Ask: \u201cWho can approve payment " + paymentId + "?\u201d to see eligible funding approvers.");
    lines.add("");
    return String.join("\n", lines);
  }

  public static String approvedReport(
      Map<String, Object> payment, ConfirmationCard card, String approverDisplay) {
    String paymentId = firstNonBlank(str(payment.get("payment_id")), card.paymentId(), "—");
    String approvedAt = firstNonBlank(str(payment.get("approved_at")), "—");
    List<String> lines = new ArrayList<>();
    lines.add("### Payment approved");
    lines.add("");
    lines.add("| Field | Value |");
    lines.add("| --- | --- |");
    lines.add("| Payment id | `" + paymentId + "` |");
    lines.add("| Instruction | `" + card.instructionId() + "` |");
    lines.add("| Value date | " + card.valueDate() + " |");
    lines.add("| Amount | " + reportAmount(payment, card) + " |");
    lines.add("| Owning LOB | **" + firstNonBlank(str(payment.get("owning_lob")), card.owningLob()) + "** |");
    lines.add("| Status | " + firstNonBlank(str(payment.get("status")), "APPROVED") + " |");
    lines.add("| Approver | " + approverDisplay + " |");
    lines.add("| Approved at | " + approvedAt + " |");
    lines.add("");
    return String.join("\n", lines);
  }

  public static String cancelledReport(
      Map<String, Object> payment, ConfirmationCard card, String cancellerDisplay) {
    String paymentId = firstNonBlank(str(payment.get("payment_id")), card.paymentId(), "—");
    String cancelledAt = firstNonBlank(str(payment.get("cancelled_at")), "—");
    List<String> lines = new ArrayList<>();
    lines.add("### Payment cancelled");
    lines.add("");
    lines.add("| Field | Value |");
    lines.add("| --- | --- |");
    lines.add("| Payment id | `" + paymentId + "` |");
    lines.add("| Instruction | `" + card.instructionId() + "` |");
    lines.add("| Value date | " + card.valueDate() + " |");
    lines.add("| Amount | " + reportAmount(payment, card) + " |");
    lines.add("| Owning LOB | **" + firstNonBlank(str(payment.get("owning_lob")), card.owningLob()) + "** |");
    lines.add("| Status | " + firstNonBlank(str(payment.get("status")), "CANCELLED") + " |");
    lines.add("| Cancelled by | " + cancellerDisplay + " |");
    lines.add("| Cancelled at | " + cancelledAt + " |");
    lines.add("");
    return String.join("\n", lines);
  }

  private static String reportAmount(Map<String, Object> payment, ConfirmationCard card) {
    double amount = asDouble(payment.get("amount"), card.amount());
    String currency = firstNonBlank(str(payment.get("currency")), card.currency());
    return formatAmount(amount, currency);
  }

  @SuppressWarnings("unchecked")
  private static String partyName(Object party) {
    if (party instanceof Map<?, ?> map) {
      Object name = ((Map<String, Object>) map).get("name");
      return name == null ? "—" : String.valueOf(name);
    }
    return "—";
  }

  @SuppressWarnings("unchecked")
  private static String accountId(Object account) {
    if (!(account instanceof Map<?, ?> map)) {
      return "—";
    }
    Map<String, Object> acct = (Map<String, Object>) map;
    String scheme = str(acct.get("identification_scheme"));
    Object ident = acct.get("identification");
    String identStr = ident == null ? "—" : String.valueOf(ident);
    if (!scheme.isBlank()) {
      return scheme + ":" + identStr;
    }
    return identStr;
  }

  @SuppressWarnings("unchecked")
  private static List<String> intermediaryLines(Map<String, Object> instruction) {
    List<String> lines = new ArrayList<>();
    Object hops = instruction.get("intermediary_agents");
    if (!(hops instanceof List<?> hopList)) {
      return lines;
    }
    int index = 0;
    for (Object hopObj : hopList) {
      index++;
      if (!(hopObj instanceof Map<?, ?> hop)) {
        continue;
      }
      Map<String, Object> hopMap = (Map<String, Object>) hop;
      Map<String, Object> agent =
          hopMap.get("agent") instanceof Map<?, ?> a ? (Map<String, Object>) a : Map.of();
      Map<String, Object> fi =
          agent.get("financial_institution") instanceof Map<?, ?> f
              ? (Map<String, Object>) f
              : agent;
      String name =
          firstNonBlank(str(fi.get("name")), str(agent.get("name")), "Intermediary " + index);
      String bic = firstNonBlank(str(fi.get("identification")), str(fi.get("bic")));
      String account = accountId(hopMap.get("account"));
      if (!bic.isBlank()) {
        lines.add(index + ". " + name + " (" + bic + ") — acct " + account);
      } else {
        lines.add(index + ". " + name + " — acct " + account);
      }
    }
    return lines;
  }

  static double asDouble(Object value, double fallback) {
    if (value instanceof Number n) {
      return n.doubleValue();
    }
    if (value != null) {
      try {
        return Double.parseDouble(String.valueOf(value));
      } catch (NumberFormatException ignored) {
        // fall through
      }
    }
    return fallback;
  }

  static int asInt(Object value, int fallback) {
    if (value instanceof Number n) {
      return n.intValue();
    }
    if (value != null) {
      try {
        return Integer.parseInt(String.valueOf(value).trim());
      } catch (NumberFormatException ignored) {
        // fall through
      }
    }
    return fallback;
  }

  static String str(Object value) {
    return value == null ? "" : String.valueOf(value);
  }

  static String firstNonBlank(String... values) {
    for (String value : values) {
      if (value != null && !value.isBlank()) {
        return value;
      }
    }
    return "";
  }

  public static String displayName(Subject subject) {
    if (subject.familyName() != null
        && !subject.familyName().isBlank()
        && subject.givenName() != null
        && !subject.givenName().isBlank()) {
      return subject.familyName() + ", " + subject.givenName();
    }
    return subject.userId();
  }

  /** Human-readable violations for denial answers (join, mirrors format_policy_violations). */
  public static String violations(List<String> violations) {
    if (violations == null || violations.isEmpty()) {
      return "policy did not allow the action";
    }
    return String.join("; ", violations);
  }

  /** Basis cell for the "yes" activity line. */
  public static String basis(List<String> allowBasis, String fallback) {
    if (allowBasis == null || allowBasis.isEmpty()) {
      return fallback;
    }
    return String.join("; ", allowBasis);
  }
}
