package com.sanjuthomas.policypilot.neo4j;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.neo4j.SecurityEventAlertListView.AlertEventRow;
import com.sanjuthomas.policypilot.neo4j.SecurityEventAlertRankingView.RankingRow;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Maps neo4j_direct planned labels + rows → Thymeleaf answer templates (parity with Python
 * planned_graph / YAML entity-detail formatters).
 */
@Component
public class Neo4jDirectAnswerFormatter {

  private static final String COUNT_TEMPLATE = "security-event-alert-count";
  private static final String LIST_TEMPLATE = "security-event-alert-list";
  private static final String RANKING_TEMPLATE = "security-event-alert-ranking";
  private static final String PAYMENT_STATUS_TEMPLATE = "payment-status-by-id";
  private static final String INSTRUCTION_STATUS_TEMPLATE = "instruction-status-by-id";
  private static final String PAYMENT_CREATOR_TEMPLATE = "payment-creator-by-id";
  private static final String APPROVAL_LOOKUP_TEMPLATE = "approval-lookup";

  private final AnswerRenderer answerRenderer;
  private final PolicyBasisFormat policyBasisFormat;

  public Neo4jDirectAnswerFormatter(
      AnswerRenderer answerRenderer, PolicyBasisFormat policyBasisFormat) {
    this.answerRenderer = answerRenderer;
    this.policyBasisFormat = policyBasisFormat;
  }

  public String format(String question, Set<String> labels, List<Map<String, Object>> rows) {
    return format(question, labels, rows, null);
  }

  public String format(
      String question, Set<String> labels, List<Map<String, Object>> rows, String intentId) {
    Set<String> labelSet = labels == null ? Set.of() : labels;
    String intent = intentId == null ? "" : intentId;

    if ("payment.status_by_id".equals(intent)
        || (labelSet.contains("payment_detail") && isStatusQuestion(question))) {
      return answerRenderer.render(PAYMENT_STATUS_TEMPLATE, toPaymentStatusView(rows));
    }
    if ("instruction.status_by_id".equals(intent)
        || (labelSet.contains("instruction_detail") && isStatusQuestion(question))) {
      return answerRenderer.render(INSTRUCTION_STATUS_TEMPLATE, toInstructionStatusView(rows));
    }
    if ("payment.creator_by_id".equals(intent)
        || (labelSet.contains("payment_detail") && isCreatorQuestion(question))) {
      return answerRenderer.render(PAYMENT_CREATOR_TEMPLATE, toPaymentCreatorView(rows));
    }
    if ("payment.approver_by_id".equals(intent)
        || "instruction.approver_by_id".equals(intent)
        || labelSet.contains("payment_approval_lookup")
        || labelSet.contains("approval_lookup")) {
      String noun =
          labelSet.contains("approval_lookup") && !labelSet.contains("payment_approval_lookup")
              ? "instruction"
              : "payment";
      if ("instruction.approver_by_id".equals(intent)) {
        noun = "instruction";
      }
      return answerRenderer.render(APPROVAL_LOOKUP_TEMPLATE, toApprovalLookupView(rows, noun));
    }

    if (labelSet.contains("ranking") && isAlertRankingQuestion(question)) {
      return answerRenderer.render(RANKING_TEMPLATE, toRankingView(question, rows));
    }
    if (labelSet.contains("security_event_alert_list") && isAlertListQuestion(question)) {
      return answerRenderer.render(LIST_TEMPLATE, toListView(question, rows));
    }
    if (labelSet.contains("count") && isAlertCountQuestion(question)) {
      return answerRenderer.render(COUNT_TEMPLATE, toCountView(question, rows));
    }
    long total = extractTotal(rows);
    return "Graph query returned " + total + " row(s).";
  }

  static boolean isStatusQuestion(String question) {
    String q = lower(question);
    return q.contains("status of")
        || q.contains("what is the status")
        || q.contains("what's the status");
  }

  static boolean isCreatorQuestion(String question) {
    String q = lower(question);
    if (q.contains("approv")) {
      return false;
    }
    return q.contains("who created") || q.contains("which user created");
  }

  static boolean isAlertCountQuestion(String question) {
    String q = lower(question);
    if (!(q.contains("how many") || q.contains("count") || q.contains("number of"))) {
      return false;
    }
    return q.contains("alert")
        || q.contains("denial")
        || q.contains("denied")
        || q.contains("security event");
  }

  static boolean isAlertListQuestion(String question) {
    String q = lower(question);
    boolean listVerb =
        q.contains("list")
            || q.contains("show")
            || q.contains("report")
            || q.contains("enumerate")
            || q.contains("display")
            || q.contains("all ");
    boolean alertNoun =
        q.contains("alert")
            || q.contains("denial")
            || q.contains("denied")
            || q.contains("security event");
    return listVerb && alertNoun;
  }

  static boolean isAlertRankingQuestion(String question) {
    String q = lower(question);
    return (q.contains("most") || q.contains("top") || q.contains("rank"))
        && (q.contains("alert") || q.contains("denial") || q.contains("denied"));
  }

  static EntityStatusByIdView toPaymentStatusView(List<Map<String, Object>> rows) {
    Map<String, Object> row = firstRow(rows);
    if (row == null) {
      return new EntityStatusByIdView(true, null, null, "");
    }
    String lob = displayOrNull(row.get("owning_lob"));
    String lobSuffix = lob == null ? "" : " (LOB " + lob + ")";
    return new EntityStatusByIdView(
        false,
        displayOrUnknown(row.get("payment_id")),
        displayOrUnknown(row.get("status")),
        lobSuffix);
  }

  static EntityStatusByIdView toInstructionStatusView(List<Map<String, Object>> rows) {
    Map<String, Object> row = firstRow(rows);
    if (row == null) {
      return new EntityStatusByIdView(true, null, null, "");
    }
    String lob = displayOrNull(row.get("owning_lob"));
    String lobSuffix = lob == null ? "" : " (LOB " + lob + ")";
    return new EntityStatusByIdView(
        false,
        displayOrUnknown(row.get("instruction_id")),
        displayOrUnknown(row.get("status")),
        lobSuffix);
  }

  static EntityCreatorByIdView toPaymentCreatorView(List<Map<String, Object>> rows) {
    Map<String, Object> row = firstRow(rows);
    if (row == null) {
      return new EntityCreatorByIdView(true, false, null, null);
    }
    String entityId = displayOrUnknown(row.get("payment_id"));
    String creator = displayOrNull(row.get("creator_display"));
    if (creator == null || "unknown".equalsIgnoreCase(creator)) {
      return new EntityCreatorByIdView(false, true, entityId, null);
    }
    return new EntityCreatorByIdView(false, false, entityId, creator);
  }

  ApprovalLookupView toApprovalLookupView(List<Map<String, Object>> rows, String entityNoun) {
    String noun = entityNoun == null || entityNoun.isBlank() ? "payment" : entityNoun;
    String displayNoun = "instruction".equalsIgnoreCase(noun) ? "Instruction" : "Payment";
    Map<String, Object> row = firstRow(rows);
    if (row == null) {
      return new ApprovalLookupView(true, false, noun, displayNoun, null, null, null, null, List.of());
    }
    String entityId =
        displayOrUnknown(
            "instruction".equalsIgnoreCase(noun) ? row.get("instruction_id") : row.get("payment_id"));
    if ("unknown".equals(entityId)) {
      entityId =
          displayOrUnknown(
              row.get("payment_id") != null ? row.get("payment_id") : row.get("instruction_id"));
    }
    if (!rowHasApproval(row)) {
      String status = displayOrUnknown(row.get("status"));
      if (!"unknown".equals(status)) {
        return new ApprovalLookupView(
            false, true, noun, displayNoun, entityId, status, null, null, List.of());
      }
      return new ApprovalLookupView(true, false, noun, displayNoun, null, null, null, null, List.of());
    }
    String who = displayOrUnknown(row.get("approver_display"));
    Object whenRaw = row.get("approved_at");
    if (whenRaw == null) {
      whenRaw = row.get("v.approved_at");
    }
    String when = displayOrNull(whenRaw);
    Object summary = row.get("authorization_summary");
    if (summary == null) {
      summary = row.get("v.authorization_summary");
    }
    Object basis = row.get("authorization_basis");
    if (basis == null) {
      basis = row.get("v.authorization_basis");
    }
    List<String> authLines =
        policyBasisFormat.formatApprovalAuthLines(
            summary == null ? null : summary.toString(), basis);
    return new ApprovalLookupView(
        false, false, noun, displayNoun, entityId, null, who, when, authLines);
  }

  static boolean rowHasApproval(Map<String, Object> row) {
    Object flag = row.get("has_approval");
    if (flag instanceof Boolean bool) {
      return bool;
    }
    if (flag != null) {
      String text = flag.toString().trim().toLowerCase(Locale.ROOT);
      if ("true".equals(text) || "false".equals(text)) {
        return Boolean.parseBoolean(text);
      }
    }
    String approver = displayOrNull(row.get("approver_display"));
    if (approver == null) {
      return false;
    }
    String lower = approver.toLowerCase(Locale.ROOT);
    return !(lower.equals("unknown") || lower.equals("—") || lower.equals("-") || lower.equals("none"));
  }

  static SecurityEventAlertCountView toCountView(String question, List<Map<String, Object>> rows) {
    String q = lower(question);
    String scopePrefix = "";
    if (q.contains("payment")) {
      scopePrefix = "payment ";
    } else if (q.contains("instruction")) {
      scopePrefix = "instruction ";
    }
    String eventLabel = (q.contains("denial") || q.contains("denied")) ? "policy denial" : "ALERT";
    String periodSuffix;
    if (q.contains("today")) {
      periodSuffix = " today";
    } else if (q.contains("this week") || q.contains("week")) {
      periodSuffix = " this week";
    } else {
      periodSuffix = "";
    }
    return new SecurityEventAlertCountView(
        extractTotal(rows), scopePrefix, eventLabel, periodSuffix);
  }

  static SecurityEventAlertListView toListView(String question, List<Map<String, Object>> rows) {
    String q = lower(question);
    boolean approvalDenial = q.contains("approval") && (q.contains("denial") || q.contains("denied"));
    String title =
        approvalDenial ? "Approval denial ALERT security events" : "ALERT security events";
    String empty =
        approvalDenial
            ? "No approval-denial ALERT security events were found in the graph."
            : "No ALERT security events were found in the graph.";
    List<AlertEventRow> tableRows = new ArrayList<>();
    if (rows != null) {
      for (Map<String, Object> row : rows) {
        if (row == null || row.get("event_id") == null) {
          continue;
        }
        tableRows.add(
            new AlertEventRow(
                display(row.get("event_id")),
                display(row.get("timestamp")),
                display(row.get("entity_type")),
                display(row.get("entity_id")),
                display(row.get("actor_display")),
                display(row.get("action"))));
      }
    }
    return new SecurityEventAlertListView(title, empty, tableRows);
  }

  static SecurityEventAlertRankingView toRankingView(
      String question, List<Map<String, Object>> rows) {
    String q = lower(question);
    String domain;
    if (q.contains("payment") && !q.contains("instruction")) {
      domain = "payment policy denial alerts";
    } else if (q.contains("instruction") && !q.contains("payment")) {
      domain = "instruction policy denial alerts";
    } else {
      domain = "policy denial alerts";
    }
    String period;
    if (q.contains("today")) {
      period = "today";
    } else if (q.contains("this week") || q.contains("week")) {
      period = "this week";
    } else {
      period = "all time";
    }
    List<RankingRow> rankingRows = new ArrayList<>();
    if (rows != null) {
      for (Map<String, Object> row : rows) {
        if (row == null || !row.containsKey("alert_count") || !row.containsKey("actor_display")) {
          continue;
        }
        rankingRows.add(
            new RankingRow(
                display(row.get("actor_display")),
                display(row.get("user_id")),
                asLong(row.get("alert_count")),
                asLong(row.get("payment_alerts")),
                asLong(row.get("instruction_alerts"))));
      }
    }
    return new SecurityEventAlertRankingView(domain, period, rankingRows);
  }

  private static Map<String, Object> firstRow(List<Map<String, Object>> rows) {
    if (rows == null || rows.isEmpty()) {
      return null;
    }
    return rows.get(0);
  }

  private static long extractTotal(List<Map<String, Object>> rows) {
    if (rows == null || rows.isEmpty()) {
      return 0L;
    }
    for (Map<String, Object> row : rows) {
      if (row != null && row.get("total") != null) {
        return asLong(row.get("total"));
      }
    }
    return rows.size();
  }

  private static long asLong(Object value) {
    if (value instanceof Number number) {
      return number.longValue();
    }
    if (value == null) {
      return 0L;
    }
    try {
      return Long.parseLong(value.toString());
    } catch (NumberFormatException ex) {
      return 0L;
    }
  }

  private static String display(Object value) {
    if (value == null) {
      return "—";
    }
    String text = value.toString();
    return text.isBlank() ? "—" : text;
  }

  private static String displayOrUnknown(Object value) {
    if (value == null) {
      return "unknown";
    }
    String text = value.toString().trim();
    return text.isEmpty() ? "unknown" : text;
  }

  private static String displayOrNull(Object value) {
    if (value == null) {
      return null;
    }
    String text = value.toString().trim();
    return text.isEmpty() ? null : text;
  }

  private static String lower(String question) {
    return question == null ? "" : question.toLowerCase(Locale.ROOT);
  }
}
