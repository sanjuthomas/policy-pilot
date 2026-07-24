package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.AuthzEvaluateException;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentClientException;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentDeniedException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;
import org.slf4j.Logger;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/**
 * Shared phase-1 + confirm skeleton for the payment-id skills (submit / approve / cancel): load
 * payment + backing instruction, status guard, OPA dry-run, pending card, then Go/No Go with a
 * fail-closed re-check before the mutation. Ports the common structure of the Python submit /
 * approve / cancel skill modules.
 */
final class PaymentIdSkillFlow {

  private PaymentIdSkillFlow() {}

  interface Mutation {
    Map<String, Object> mutate(String paymentId, Subject subject);

    String successReport(Map<String, Object> payment, PendingSkill pending, Subject subject);

    String successVerb();

    String successStatus();
  }

  static Predicate<String> statusEquals(String status) {
    return value -> status.equals(value);
  }

  static Predicate<String> statusIn(String... statuses) {
    return value -> {
      for (String s : statuses) {
        if (s.equals(value)) {
          return true;
        }
      }
      return false;
    };
  }

  static SkillRunResult phase1(
      String skill,
      String action,
      String paymentId,
      Subject subject,
      List<String> activities,
      EligibilityClient eligibilityClient,
      AuthzPaymentEvaluateClient authzClient,
      PendingSkillStore store,
      Predicate<String> statusOk,
      String wrongStatusExtra,
      String nothingClause,
      String phase1Answer) {
    String verb = action.toLowerCase(java.util.Locale.ROOT);
    if (isBlank(subject.bearerToken())) {
      return SkillRunResult.terminal(
          "Sign-in token missing — cannot load the payment or evaluate policy.",
          List.of("Missing user session token."),
          "skill." + skill + ".auth_error",
          skill);
    }

    activities.add("Parsed request: " + verb + " payment `" + paymentId + "`.");

    Map<String, Object> payment;
    try {
      payment = eligibilityClient.getPayment(paymentId, subject.bearerToken(), subject.sessionId());
    } catch (ResponseStatusException ex) {
      if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
        return SkillRunResult.terminal(
            "**Stopped** — payment `" + paymentId + "` was not found. " + nothingClause,
            activities,
            "skill." + skill + ".payment_missing",
            skill);
      }
      return SkillRunResult.terminal(
          "**Stopped** — could not load the payment (" + ex.getReason() + ").",
          activities,
          "skill." + skill + ".payment_error",
          skill);
    }

    String paymentStatus = SkillFormat.str(payment.get("status"));
    String instructionId = SkillFormat.str(payment.get("instruction_id"));
    double amount = SkillFormat.asDouble(payment.get("amount"), 0);
    String currency = SkillFormat.firstNonBlank(SkillFormat.str(payment.get("currency")), "USD");
    String owningLob = SkillFormat.firstNonBlank(SkillFormat.str(payment.get("owning_lob")), "—");
    String valueDate = SkillFormat.str(payment.get("value_date"));
    activities.add(
        "Loaded payment `"
            + paymentId
            + "` — status **"
            + paymentStatus
            + "**, LOB **"
            + owningLob
            + "**, amount **"
            + SkillFormat.formatAmount(amount, currency)
            + "**.");

    if (!statusOk.test(paymentStatus)) {
      return SkillRunResult.terminal(
          "**Stopped** — payment `" + paymentId + "` is **" + paymentStatus + "**. " + wrongStatusExtra,
          activities,
          "skill." + skill + ".wrong_status",
          skill);
    }

    if (isBlank(instructionId)) {
      return SkillRunResult.terminal(
          "**Stopped** — payment is missing an instruction id.",
          List.of("Payment had no instruction_id."),
          "skill." + skill + ".instruction_missing",
          skill);
    }

    Map<String, Object> instruction;
    try {
      instruction =
          eligibilityClient.getInstruction(instructionId, subject.bearerToken(), subject.sessionId());
    } catch (ResponseStatusException ex) {
      if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
        return SkillRunResult.terminal(
            "**Stopped** — backing instruction `"
                + instructionId
                + "` was not found. "
                + nothingClause,
            activities,
            "skill." + skill + ".instruction_missing",
            skill);
      }
      return SkillRunResult.terminal(
          "**Stopped** — could not load the backing instruction (" + ex.getReason() + ").",
          activities,
          "skill." + skill + ".instruction_error",
          skill);
    }

    String instructionStatus = SkillFormat.str(instruction.get("status"));
    String instructionEndDate = SkillFormat.str(instruction.get("end_date"));
    activities.add(
        "Loaded instruction `"
            + instructionId
            + "` — status **"
            + instructionStatus
            + "**, owning LOB **"
            + owningLob
            + "**.");
    activities.add(
        "Checking if `"
            + subject.userId()
            + "` ("
            + SkillFormat.displayName(subject)
            + ") may **"
            + action
            + "** payment `"
            + paymentId
            + "`…");

    Map<String, Object> opaPayload =
        opaPaymentPayload(payment, instruction, defaultOpaStatus(action));
    PolicyDecision decision;
    try {
      decision = authzClient.evaluate(action, opaPayload, instructionStatus, instructionEndDate, subject);
    } catch (AuthzEvaluateException ex) {
      return SkillRunResult.terminal(
          "**Stopped** — could not evaluate " + action + " permission (" + ex.getMessage() + ").",
          activities,
          "skill." + skill + ".evaluate_error",
          skill);
    }

    if (!decision.allowed()) {
      activities.add("**Denied** — " + SkillFormat.violations(decision.violations()));
      return SkillRunResult.terminal(
          "**No** — `"
              + subject.userId()
              + "` may not "
              + verb
              + " this payment under policy.\n\nViolations: "
              + SkillFormat.violations(decision.violations())
              + "\n\n"
              + nothingClause,
          activities,
          "skill." + skill + ".denied",
          skill);
    }

    activities.add(
        "**Yes** — `"
            + subject.userId()
            + "` ("
            + SkillFormat.displayName(subject)
            + ") may "
            + verb
            + " this payment. Basis: "
            + SkillFormat.basis(decision.allowBasis(), action + " allowed"));

    ConfirmationCard card =
        SkillFormat.cardFromInstruction(instruction, amount, valueDate, paymentId, paymentStatus);
    Map<String, Object> createdBy =
        payment.get("created_by") instanceof Map<?, ?> m ? castMap(m) : Map.of();
    int instructionVersion =
        SkillFormat.asInt(
            payment.get("instruction_version"),
            SkillFormat.asInt(instruction.get("version_number"), 1));
    PendingSkill pending =
        new PendingSkill(
            store.newPendingId(),
            skill,
            subject.userId(),
            paymentId,
            instructionId,
            amount,
            valueDate,
            currency,
            owningLob,
            paymentStatus,
            instructionStatus,
            instructionEndDate,
            SkillFormat.firstNonBlank(
                SkillFormat.str(payment.get("instruction_type")),
                SkillFormat.str(instruction.get("instruction_type"))),
            instructionVersion,
            SkillFormat.str(createdBy.get("user_id")),
            createdBy.get("supervisor_id") == null ? null : String.valueOf(createdBy.get("supervisor_id")),
            card,
            store.defaultExpiresAt());
    store.put(pending);

    return SkillRunResult.awaiting(
        phase1Answer,
        activities,
        pending.pendingId(),
        card,
        "skill." + skill + ".awaiting_confirmation",
        skill);
  }

  static SkillRunResult confirm(
      String skill,
      String action,
      String pendingId,
      String decision,
      Subject subject,
      AuthzPaymentEvaluateClient authzClient,
      PendingSkillStore store,
      String noGoAnswer,
      String noGoIntent,
      String nothingClause,
      Mutation mutation,
      Logger log) {
    String verb = action.toLowerCase(java.util.Locale.ROOT);
    PendingSkill pending = store.get(pendingId);
    if (pending == null || !skill.equals(pending.skill())) {
      return SkillRunResult.terminal(
          "That confirmation expired or was already used. "
              + "Ask again to "
              + verb
              + " the payment if you still need it.",
          List.of("Pending skill not found or expired."),
          "skill." + skill + ".pending_missing",
          skill);
    }
    if (!pending.userId().equals(subject.userId())) {
      return SkillRunResult.terminal(
          "This confirmation belongs to another user. " + nothingClause,
          List.of("Pending skill user mismatch."),
          "skill." + skill + ".pending_forbidden",
          skill);
    }
    if ("no_go".equals(decision)) {
      store.pop(pendingId);
      return SkillRunResult.terminal(
          noGoAnswer, List.of("User selected No Go — pending " + verb + " discarded."), noGoIntent, skill);
    }
    if (!"go".equals(decision)) {
      return SkillRunResult.terminal(
          "Decision must be `\"go\"` or `\"no_go\"`.",
          List.of("Invalid decision: " + decision),
          "skill." + skill + ".bad_decision",
          skill);
    }
    if (isBlank(subject.bearerToken())) {
      return SkillRunResult.terminal(
          "Sign-in token missing — cannot " + verb + " the payment.",
          List.of("Missing user session token on confirm."),
          "skill." + skill + ".auth_error",
          skill);
    }

    pending = store.pop(pendingId);
    if (pending == null) {
      return SkillRunResult.terminal(
          "That confirmation was already used. No additional " + verb + " was sent.",
          List.of("Pending skill already consumed."),
          "skill." + skill + ".pending_missing",
          skill);
    }

    List<String> activities = new ArrayList<>();
    activities.add("Go selected — " + verb + " payment `" + pending.paymentId() + "`…");

    Map<String, Object> opaPayload = new LinkedHashMap<>();
    opaPayload.put("payment_id", pending.paymentId());
    opaPayload.put("instruction_id", pending.instructionId());
    opaPayload.put("instruction_version", pending.instructionVersion());
    opaPayload.put("status", pending.paymentStatus());
    opaPayload.put("amount", pending.amount());
    opaPayload.put("currency", pending.currency());
    opaPayload.put("instruction_status", pending.instructionStatus());
    opaPayload.put("instruction_end_date", pending.instructionEndDate());
    opaPayload.put("instruction_type", pending.instructionType());
    opaPayload.put("instruction_owning_lob", pending.owningLob());
    Map<String, Object> createdBy = new LinkedHashMap<>();
    createdBy.put("user_id", pending.createdByUserId());
    createdBy.put("supervisor_id", pending.createdBySupervisorId());
    opaPayload.put("created_by", createdBy);
    try {
      PolicyDecision recheck =
          authzClient.evaluate(
              action, opaPayload, pending.instructionStatus(), pending.instructionEndDate(), subject);
      if (!recheck.allowed()) {
        activities.add("Re-check denied " + action + ": " + SkillFormat.violations(recheck.violations()));
        return SkillRunResult.terminal(
            "**Stopped before "
                + verb
                + "** — policy no longer allows "
                + action
                + " ("
                + SkillFormat.violations(recheck.violations())
                + "). "
                + nothingClause,
            activities,
            "skill." + skill + ".recheck_denied",
            skill);
      }
    } catch (AuthzEvaluateException ex) {
      log.warn("{} confirm recheck failed: {} — aborting {}", skill, ex.toString(), verb);
      activities.add("Could not re-check policy (" + ex.getMessage() + ") — stopped before " + verb + ".");
      return SkillRunResult.terminal(
          "**Stopped before "
              + verb
              + "** — could not re-check "
              + action
              + " permission ("
              + ex.getMessage()
              + "). "
              + nothingClause,
          activities,
          "skill." + skill + ".recheck_error",
          skill);
    }

    Map<String, Object> payment;
    try {
      payment = mutation.mutate(pending.paymentId(), subject);
    } catch (PaymentDeniedException ex) {
      activities.add(action + " denied by payment-service: " + ex.detail());
      return SkillRunResult.terminal(
          "**" + label(verb) + " denied** — " + ex.detail() + "\n\nNothing was persisted.",
          activities,
          "skill." + skill + "." + verb + "_denied",
          skill);
    } catch (PaymentClientException ex) {
      activities.add(action + " failed: " + ex.getMessage());
      return SkillRunResult.terminal(
          "**" + label(verb) + " failed** — " + ex.getMessage(),
          activities,
          "skill." + skill + "." + verb + "_error",
          skill);
    }

    activities.add(
        mutation.successVerb()
            + " payment `"
            + SkillFormat.firstNonBlank(SkillFormat.str(payment.get("payment_id")), pending.paymentId())
            + "` (status "
            + mutation.successStatus()
            + ").");
    return SkillRunResult.terminal(
        mutation.successReport(payment, pending, subject),
        activities,
        "skill." + skill + "." + mutation.successStatus().toLowerCase(java.util.Locale.ROOT),
        skill);
  }

  private static String defaultOpaStatus(String action) {
    return "APPROVE".equals(action) ? "SUBMITTED" : "DRAFT";
  }

  static Map<String, Object> opaPaymentPayload(
      Map<String, Object> payment, Map<String, Object> instruction, String defaultStatus) {
    Map<String, Object> createdBy =
        payment.get("created_by") instanceof Map<?, ?> m ? castMap(m) : Map.of();
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("payment_id", payment.get("payment_id"));
    payload.put("instruction_id", payment.get("instruction_id"));
    payload.put(
        "instruction_version",
        SkillFormat.asInt(
            payment.get("instruction_version"),
            SkillFormat.asInt(instruction.get("version_number"), 1)));
    payload.put("status", SkillFormat.firstNonBlank(SkillFormat.str(payment.get("status")), defaultStatus));
    payload.put("amount", payment.get("amount"));
    payload.put(
        "currency",
        SkillFormat.firstNonBlank(
            SkillFormat.str(payment.get("currency")), SkillFormat.str(instruction.get("currency"))));
    payload.put("instruction_status", SkillFormat.str(instruction.get("status")));
    payload.put("instruction_end_date", SkillFormat.str(instruction.get("end_date")));
    payload.put(
        "instruction_type",
        SkillFormat.firstNonBlank(
            SkillFormat.str(payment.get("instruction_type")),
            SkillFormat.str(instruction.get("instruction_type"))));
    payload.put(
        "instruction_owning_lob",
        SkillFormat.firstNonBlank(
            SkillFormat.str(payment.get("owning_lob")), SkillFormat.str(instruction.get("owning_lob"))));
    Map<String, Object> cb = new LinkedHashMap<>();
    cb.put("user_id", SkillFormat.str(createdBy.get("user_id")));
    cb.put("supervisor_id", createdBy.get("supervisor_id"));
    payload.put("created_by", cb);
    return payload;
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> castMap(Map<?, ?> map) {
    return (Map<String, Object>) map;
  }

  private static String label(String verb) {
    return verb.substring(0, 1).toUpperCase(java.util.Locale.ROOT) + verb.substring(1);
  }

  private static boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
