package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.neo4j.ApprovalLookupView;
import com.sanjuthomas.policypilot.neo4j.EntityCreatorAndApproverView;
import com.sanjuthomas.policypilot.neo4j.EntityCreatorByIdView;
import com.sanjuthomas.policypilot.neo4j.EntityStatusByIdView;
import com.sanjuthomas.policypilot.neo4j.InstructionInventoryTableView;
import com.sanjuthomas.policypilot.neo4j.InstructionInventoryTableView.InventoryRow;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * Facet formatters for entity document_extraction answers (status / creator / approver /
 * inventory / versions) — same Thymeleaf templates previously used on the neo4j_direct lane.
 */
@Component
public class EntityApiAnswerFormatter {

  private static final String PAYMENT_STATUS = "payment-status-by-id";
  private static final String INSTRUCTION_STATUS = "instruction-status-by-id";
  private static final String PAYMENT_CREATOR = "payment-creator-by-id";
  private static final String INSTRUCTION_CREATOR = "instruction-creator-by-id";
  private static final String CREATOR_AND_APPROVER = "entity-creator-and-approver";
  private static final String APPROVAL_LOOKUP = "approval-lookup";
  private static final String INVENTORY = "instruction-inventory-table";
  private static final String INSTRUCTION_VERSIONS = "instruction-versions-table";
  private static final String PAYMENT_VERSIONS = "payment-versions-table";

  private final AnswerRenderer answerRenderer;
  private final PolicyBasisFormat policyBasisFormat;

  public EntityApiAnswerFormatter(
      AnswerRenderer answerRenderer, PolicyBasisFormat policyBasisFormat) {
    this.answerRenderer = answerRenderer;
    this.policyBasisFormat = policyBasisFormat;
  }

  public String formatPaymentStatus(Map<String, Object> data) {
    return answerRenderer.render(PAYMENT_STATUS, toStatusView(data, "payment_id"));
  }

  public String formatInstructionStatus(Map<String, Object> data) {
    return answerRenderer.render(INSTRUCTION_STATUS, toStatusView(data, "instruction_id"));
  }

  public String formatPaymentCreator(Map<String, Object> data) {
    return answerRenderer.render(PAYMENT_CREATOR, toCreatorView(data, "payment_id"));
  }

  public String formatInstructionCreator(Map<String, Object> data) {
    return answerRenderer.render(INSTRUCTION_CREATOR, toCreatorView(data, "instruction_id"));
  }

  public String formatPaymentCreatorAndApprover(Map<String, Object> data) {
    return answerRenderer.render(
        CREATOR_AND_APPROVER, toCreatorAndApproverView(data, "Payment", "payment_id"));
  }

  public String formatInstructionCreatorAndApprover(Map<String, Object> data) {
    return answerRenderer.render(
        CREATOR_AND_APPROVER, toCreatorAndApproverView(data, "Instruction", "instruction_id"));
  }

  public String formatPaymentApprover(Map<String, Object> data) {
    return answerRenderer.render(APPROVAL_LOOKUP, toApprovalLookupView(data, "payment"));
  }

  public String formatInstructionApprover(Map<String, Object> data) {
    return answerRenderer.render(APPROVAL_LOOKUP, toApprovalLookupView(data, "instruction"));
  }

  public String formatInstructionInventory(List<Map<String, Object>> rows) {
    return answerRenderer.render(INVENTORY, toInventoryView(rows));
  }

  public String formatInstructionVersions(String instructionId, List<Map<String, Object>> rows) {
    return answerRenderer.render(
        INSTRUCTION_VERSIONS, toVersionsView(instructionId, rows, false));
  }

  public String formatPaymentVersions(String paymentId, List<Map<String, Object>> rows) {
    return answerRenderer.render(PAYMENT_VERSIONS, toVersionsView(paymentId, rows, true));
  }

  static EntityStatusByIdView toStatusView(Map<String, Object> data, String idKey) {
    if (data == null || data.isEmpty()) {
      return new EntityStatusByIdView(true, null, null, "");
    }
    String lob = displayOrNull(data.get("owning_lob"));
    String lobSuffix = lob == null ? "" : " (LOB " + lob + ")";
    return new EntityStatusByIdView(
        false, displayOrUnknown(data.get(idKey)), displayOrUnknown(data.get("status")), lobSuffix);
  }

  static EntityCreatorByIdView toCreatorView(Map<String, Object> data, String idKey) {
    if (data == null || data.isEmpty()) {
      return new EntityCreatorByIdView(true, false, null, null);
    }
    String entityId = displayOrUnknown(data.get(idKey));
    String creator = EntityUserDisplay.creator(data.get("created_by"));
    if (!StringUtils.hasText(creator) || "—".equals(creator)) {
      return new EntityCreatorByIdView(false, true, entityId, null);
    }
    return new EntityCreatorByIdView(false, false, entityId, creator);
  }

  ApprovalLookupView toApprovalLookupView(Map<String, Object> data, String entityNoun) {
    String noun = entityNoun == null || entityNoun.isBlank() ? "payment" : entityNoun;
    String displayNoun = "instruction".equalsIgnoreCase(noun) ? "Instruction" : "Payment";
    String idKey = "instruction".equalsIgnoreCase(noun) ? "instruction_id" : "payment_id";
    if (data == null || data.isEmpty()) {
      return new ApprovalLookupView(true, false, noun, displayNoun, null, null, null, null, List.of());
    }
    String entityId = displayOrUnknown(data.get(idKey));
    String who = displayApprover(data.get("approved_by"));
    if ("—".equals(who)) {
      return new ApprovalLookupView(
          false,
          true,
          noun,
          displayNoun,
          entityId,
          displayOrUnknown(data.get("status")),
          null,
          null,
          List.of());
    }
    String when = displayOrNull(data.get("approved_at"));
    String summary = authorizationSummary(data, who);
    Object basis = authorizationBasis(data);
    List<String> authLines = policyBasisFormat.formatApprovalAuthLines(summary, basis);
    return new ApprovalLookupView(
        false, false, noun, displayNoun, entityId, null, who, when, authLines);
  }

  static EntityCreatorAndApproverView toCreatorAndApproverView(
      Map<String, Object> data, String displayNoun, String idKey) {
    String noun = displayNoun == null || displayNoun.isBlank() ? "Payment" : displayNoun;
    String entityNoun = noun.toLowerCase(Locale.ROOT);
    if (data == null || data.isEmpty()) {
      return new EntityCreatorAndApproverView(true, noun, entityNoun, null, null, null, null);
    }
    String entityId = displayOrUnknown(data.get(idKey));
    String creator = EntityUserDisplay.creator(data.get("created_by"));
    String approver = EntityUserDisplay.approver(data.get("approved_by"));
    if ("— (not yet approved)".equals(approver)) {
      approver = "—";
    }
    String approvedAt = displayOrNull(data.get("approved_at"));
    return new EntityCreatorAndApproverView(
        false, noun, entityNoun, entityId, creator, approver, approvedAt);
  }

  static InstructionInventoryTableView toInventoryView(List<Map<String, Object>> rows) {
    List<InventoryRow> tableRows = new ArrayList<>();
    if (rows != null) {
      for (Map<String, Object> row : rows) {
        if (row == null || row.get("instruction_id") == null) {
          continue;
        }
        tableRows.add(
            new InventoryRow(
                display(row.get("instruction_id")),
                display(row.get("status")),
                display(row.get("owning_lob")),
                display(row.get("currency")),
                display(EntityUserDisplay.creator(row.get("created_by"))),
                displayApprover(row.get("approved_by"))));
      }
    }
    return new InstructionInventoryTableView(
        "No matching instructions were found.", tableRows);
  }

  static EntityVersionsTableView toVersionsView(
      String entityId, List<Map<String, Object>> rows, boolean payment) {
    List<EntityVersionsTableView.VersionRow> tableRows = new ArrayList<>();
    if (rows != null) {
      for (Map<String, Object> row : rows) {
        if (row == null) {
          continue;
        }
        tableRows.add(
            new EntityVersionsTableView.VersionRow(
                display(row.get("version_number")),
                display(row.get("status")),
                payment ? display(row.get("amount")) : null,
                payment ? display(row.get("currency")) : null,
                display(row.get("created_at")),
                display(EntityUserDisplay.creator(row.get("created_by"))),
                displayApprover(row.get("approved_by"))));
      }
    }
    String id = StringUtils.hasText(entityId) ? entityId : "unknown";
    String empty =
        payment
            ? "No payment versions were found."
            : "No instruction versions were found.";
    return new EntityVersionsTableView(id, empty, payment, tableRows);
  }

  private static String displayApprover(Object approvedBy) {
    String text = EntityUserDisplay.approver(approvedBy);
    return "— (not yet approved)".equals(text) ? "—" : text;
  }

  @SuppressWarnings("unchecked")
  private static String authorizationSummary(Map<String, Object> data, String who) {
    Map<String, Object> auth = approveAuthorization(data);
    if (auth != null) {
      Object summary = auth.get("summary");
      if (summary != null && !summary.toString().isBlank()) {
        return summary.toString().strip();
      }
    }
    // Instruction GET has no lifecycle_events; synthesize from approved_by roles.
    Object approvedBy = data.get("approved_by");
    if (!(approvedBy instanceof Map<?, ?> map)) {
      return null;
    }
    Object rolesRaw = map.get("roles");
    if (!(rolesRaw instanceof List<?> roles) || roles.isEmpty()) {
      return null;
    }
    String role =
        roles.stream()
            .filter(r -> r != null && !r.toString().isBlank())
            .map(Object::toString)
            .findFirst()
            .orElse(null);
    if (role == null) {
      return null;
    }
    return who + " was allowed to APPROVE because role " + role;
  }

  private static Object authorizationBasis(Map<String, Object> data) {
    Map<String, Object> auth = approveAuthorization(data);
    return auth == null ? null : auth.get("allow_basis");
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> approveAuthorization(Map<String, Object> data) {
    Object events = data.get("lifecycle_events");
    if (!(events instanceof List<?> list)) {
      return null;
    }
    for (int i = list.size() - 1; i >= 0; i--) {
      Object item = list.get(i);
      if (!(item instanceof Map<?, ?> event)) {
        continue;
      }
      Object action = event.get("action");
      if (action == null || !"APPROVE".equalsIgnoreCase(action.toString())) {
        continue;
      }
      Object details = event.get("details");
      if (!(details instanceof Map<?, ?> detailsMap)) {
        return null;
      }
      Object authorization = detailsMap.get("authorization");
      if (authorization instanceof Map<?, ?> authMap) {
        return (Map<String, Object>) authMap;
      }
      return null;
    }
    return null;
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
}
