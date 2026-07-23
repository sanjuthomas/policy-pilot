package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
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
 * Facet formatters for entity document_extraction answers (status / creator / inventory /
 * versions) — same Thymeleaf templates previously used on the neo4j_direct lane.
 */
@Component
public class EntityApiAnswerFormatter {

  private static final String PAYMENT_STATUS = "payment-status-by-id";
  private static final String INSTRUCTION_STATUS = "instruction-status-by-id";
  private static final String PAYMENT_CREATOR = "payment-creator-by-id";
  private static final String INSTRUCTION_CREATOR = "instruction-creator-by-id";
  private static final String CREATOR_AND_APPROVER = "entity-creator-and-approver";
  private static final String INVENTORY = "instruction-inventory-table";
  private static final String INSTRUCTION_VERSIONS = "instruction-versions-table";
  private static final String PAYMENT_VERSIONS = "payment-versions-table";

  private final AnswerRenderer answerRenderer;

  public EntityApiAnswerFormatter(AnswerRenderer answerRenderer) {
    this.answerRenderer = answerRenderer;
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
