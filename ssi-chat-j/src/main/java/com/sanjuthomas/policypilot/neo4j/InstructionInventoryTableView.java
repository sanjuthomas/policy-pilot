package com.sanjuthomas.policypilot.neo4j;

import java.util.List;

/** View model for {@code templates/answers/instruction-inventory-table.md}. */
public record InstructionInventoryTableView(String emptyMessage, List<InventoryRow> rows) {

  public record InventoryRow(
      String instructionId,
      String status,
      String owningLob,
      String currency,
      String creatorDisplay,
      String approverDisplay) {}
}
