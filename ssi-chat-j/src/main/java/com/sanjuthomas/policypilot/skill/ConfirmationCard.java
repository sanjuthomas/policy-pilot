package com.sanjuthomas.policypilot.skill;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Payment confirmation card shown with a phase-1 skill {@code awaiting_confirmation} response.
 * Mirrors Python {@code chat_application.skills.models.ConfirmationCard.to_api()}.
 */
public record ConfirmationCard(
    String instructionId,
    double amount,
    String currency,
    String valueDate,
    String owningLob,
    String instructionStatus,
    String debtorName,
    String debtorAccount,
    String creditorName,
    String creditorAccount,
    List<String> intermediaries,
    String paymentId,
    String paymentStatus) {

  public ConfirmationCard {
    intermediaries = intermediaries == null ? List.of() : List.copyOf(intermediaries);
  }

  /** Serialized shape for {@code skill_confirmation.card} — parity with Python {@code to_api}. */
  public Map<String, Object> toApi() {
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("instruction_id", instructionId);
    payload.put("amount", amount);
    payload.put("currency", currency);
    payload.put("value_date", valueDate);
    payload.put("owning_lob", owningLob);
    payload.put("instruction_status", instructionStatus);
    payload.put("debtor_name", debtorName);
    payload.put("debtor_account", debtorAccount);
    payload.put("creditor_name", creditorName);
    payload.put("creditor_account", creditorAccount);
    payload.put("intermediaries", new ArrayList<>(intermediaries));
    if (paymentId != null && !paymentId.isBlank()) {
      payload.put("payment_id", paymentId);
    }
    if (paymentStatus != null && !paymentStatus.isBlank()) {
      payload.put("payment_status", paymentStatus);
    }
    return payload;
  }
}
