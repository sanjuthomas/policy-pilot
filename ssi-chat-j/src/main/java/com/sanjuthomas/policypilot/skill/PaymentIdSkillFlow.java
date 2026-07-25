package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.AuthzEvaluateException;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.EvaluateExchange;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentClientException;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentDeniedException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Predicate;
import org.slf4j.Logger;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/**
 * Shared phase-1 + confirm skeleton for the payment-id skills (submit / approve / cancel): load
 * payment + backing instruction, status guard, OPA dry-run, pending card, then Go/No Go with a
 * fail-closed re-check before the mutation. Persists governed activity audits (linked to OPA
 * security events on mutate).
 */
final class PaymentIdSkillFlow {

  private PaymentIdSkillFlow() {}

  interface Mutation {
    Map<String, Object> mutate(String paymentId, Subject subject, String auditExecutionId);

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
      AuditExecutionClient auditClient,
      PendingSkillStore store,
      Predicate<String> statusOk,
      String wrongStatusExtra,
      String nothingClause,
      String phase1Answer) {
    String verb = action.toLowerCase(Locale.ROOT);
    long started = System.currentTimeMillis();
    List<Map<String, Object>> timeline = new ArrayList<>();
    timeline.add(
        AuditExecutionClient.timelineStep(
            "identity",
            "Subject `" + subject.userId() + "` established for " + skill + ".",
            "info",
            nowIso()));

    if (isBlank(subject.bearerToken())) {
      return SkillRunResult.terminal(
          "Sign-in token missing — cannot load the payment or evaluate policy.",
          List.of("Missing user session token."),
          "skill." + skill + ".auth_error",
          skill);
    }

    activities.add("Parsed request: " + verb + " payment `" + paymentId + "`.");
    timeline.add(
        AuditExecutionClient.timelineStep(
            "request", "Parsed " + verb + " request for `" + paymentId + "`.", "info", nowIso()));

    Map<String, Object> payment;
    try {
      payment = eligibilityClient.getPayment(paymentId, subject.bearerToken(), subject.sessionId());
    } catch (ResponseStatusException ex) {
      if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
        timeline.add(
            AuditExecutionClient.timelineStep(
                "payment", "Payment not found.", "deny", nowIso()));
        persistTerminalAudit(
            auditClient,
            skill,
            action,
            subject,
            Map.of("payment_id", paymentId),
            "DENIED",
            "deny",
            "skill." + skill + ".payment_missing",
            timeline,
            Map.of("total", System.currentTimeMillis() - started),
            null,
            Map.of("message", "payment not found"));
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
    Map<String, Object> request = requestFromPayment(payment);
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
    timeline.add(
        AuditExecutionClient.timelineStep(
            "payment",
            "Loaded payment `" + paymentId + "` (" + paymentStatus + ").",
            "info",
            nowIso()));

    if (!statusOk.test(paymentStatus)) {
      timeline.add(
          AuditExecutionClient.timelineStep(
              "status_guard",
              "Wrong status " + paymentStatus + ".",
              "deny",
              nowIso()));
      persistTerminalAudit(
          auditClient,
          skill,
          action,
          subject,
          request,
          "DENIED",
          "deny",
          "skill." + skill + ".wrong_status",
          timeline,
          Map.of("total", System.currentTimeMillis() - started),
          null,
          Map.of("message", "wrong status", "status", paymentStatus));
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
        timeline.add(
            AuditExecutionClient.timelineStep(
                "instruction", "Backing instruction not found.", "deny", nowIso()));
        persistTerminalAudit(
            auditClient,
            skill,
            action,
            subject,
            request,
            "DENIED",
            "deny",
            "skill." + skill + ".instruction_missing",
            timeline,
            Map.of("total", System.currentTimeMillis() - started),
            null,
            Map.of("message", "instruction not found", "instruction_id", instructionId));
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
    timeline.add(
        AuditExecutionClient.timelineStep(
            "instruction",
            "Loaded instruction `" + instructionId + "` (" + instructionStatus + ").",
            "info",
            nowIso()));
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
    EvaluateExchange exchange;
    try {
      exchange =
          authzClient.evaluateExchange(
              action, opaPayload, instructionStatus, instructionEndDate, subject);
    } catch (AuthzEvaluateException ex) {
      timeline.add(
          AuditExecutionClient.timelineStep(
              "preflight_opa",
              action + " evaluate failed: " + ex.getMessage(),
              "error",
              nowIso()));
      persistTerminalAudit(
          auditClient,
          skill,
          action,
          subject,
          request,
          "FAILED",
          "error",
          "skill." + skill + ".evaluate_error",
          timeline,
          Map.of("total", System.currentTimeMillis() - started),
          null,
          Map.of("message", ex.getMessage()));
      return SkillRunResult.terminal(
          "**Stopped** — could not evaluate " + action + " permission (" + ex.getMessage() + ").",
          activities,
          "skill." + skill + ".evaluate_error",
          skill);
    }

    PolicyDecision decision = exchange.decision();
    if (!decision.allowed()) {
      activities.add("**Denied** — " + SkillFormat.violations(decision.violations()));
      timeline.add(
          AuditExecutionClient.timelineStep(
              "preflight_opa",
              action + " denied: " + SkillFormat.violations(decision.violations()),
              "deny",
              nowIso()));
      persistTerminalAudit(
          auditClient,
          skill,
          action,
          subject,
          request,
          "DENIED",
          "deny",
          "skill." + skill + ".denied",
          timeline,
          Map.of("total", System.currentTimeMillis() - started),
          AuditExecutionClient.policyExchange(exchange.request(), exchange.response()),
          Map.of("message", action + " denied", "violations", decision.violations()));
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
    timeline.add(
        AuditExecutionClient.timelineStep(
            "preflight_opa",
            action
                + " allowed. Basis: "
                + SkillFormat.basis(decision.allowBasis(), action + " allowed"),
            "allow",
            nowIso()));

    ConfirmationCard card =
        SkillFormat.cardFromInstruction(instruction, amount, valueDate, paymentId, paymentStatus);
    Map<String, Object> createdBy =
        payment.get("created_by") instanceof Map<?, ?> m ? castMap(m) : Map.of();
    int instructionVersion =
        SkillFormat.asInt(
            payment.get("instruction_version"),
            SkillFormat.asInt(instruction.get("version_number"), 1));
    String auditExecutionId =
        persistAwaitingAudit(
            auditClient,
            skill,
            action,
            subject,
            request,
            timeline,
            Map.of("total", System.currentTimeMillis() - started),
            AuditExecutionClient.policyExchange(exchange.request(), exchange.response()));
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
            createdBy.get("supervisor_id") == null
                ? null
                : String.valueOf(createdBy.get("supervisor_id")),
            card,
            store.defaultExpiresAt(),
            auditExecutionId);
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
      AuditExecutionClient auditClient,
      PendingSkillStore store,
      String noGoAnswer,
      String noGoIntent,
      String nothingClause,
      Mutation mutation,
      Logger log) {
    String verb = action.toLowerCase(Locale.ROOT);
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
      patchAudit(
          auditClient,
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "CANCELLED",
              "outcome",
              "cancelled",
              "result",
              resultWithPaymentId(
                  Map.of("payment_id", pending.paymentId()),
                  Map.of("message", "user selected No Go")),
              "timeline",
              List.of(
                  AuditExecutionClient.timelineStep(
                      "confirmation", "User selected No Go.", "cancelled", nowIso()))));
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
      EvaluateExchange recheck =
          authzClient.evaluateExchange(
              action, opaPayload, pending.instructionStatus(), pending.instructionEndDate(), subject);
      if (!recheck.decision().allowed()) {
        activities.add(
            "Re-check denied " + action + ": " + SkillFormat.violations(recheck.decision().violations()));
        patchAudit(
            auditClient,
            pending.auditExecutionId(),
            subject,
            Map.of(
                "status",
                "DENIED",
                "outcome",
                "deny",
                "governance",
                Map.of(
                    "policy_exchange",
                    AuditExecutionClient.policyExchange(recheck.request(), recheck.response())),
                "result",
                resultWithPaymentId(
                    Map.of("payment_id", pending.paymentId()),
                    Map.of(
                        "message",
                        "recheck denied",
                        "violations",
                        recheck.decision().violations())),
                "timeline",
                List.of(
                    AuditExecutionClient.timelineStep(
                        "recheck_opa",
                        "Re-check denied " + action + ".",
                        "deny",
                        nowIso()))));
        return SkillRunResult.terminal(
            "**Stopped before "
                + verb
                + "** — policy no longer allows "
                + action
                + " ("
                + SkillFormat.violations(recheck.decision().violations())
                + "). "
                + nothingClause,
            activities,
            "skill." + skill + ".recheck_denied",
            skill);
      }
    } catch (AuthzEvaluateException ex) {
      log.warn("{} confirm recheck failed: {} — aborting {}", skill, ex.toString(), verb);
      activities.add("Could not re-check policy (" + ex.getMessage() + ") — stopped before " + verb + ".");
      patchAudit(
          auditClient,
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "FAILED",
              "outcome",
              "error",
              "result",
              resultWithPaymentId(
                  Map.of("payment_id", pending.paymentId()),
                  Map.of("message", "recheck failed: " + ex.getMessage())),
              "timeline",
              List.of(
                  AuditExecutionClient.timelineStep(
                      "recheck_opa",
                      "Re-check failed: " + ex.getMessage(),
                      "error",
                      nowIso()))));
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
      payment = mutation.mutate(pending.paymentId(), subject, pending.auditExecutionId());
    } catch (PaymentDeniedException ex) {
      activities.add(action + " denied by payment-service: " + ex.detail());
      patchAudit(
          auditClient,
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "DENIED",
              "outcome",
              "deny",
              "result",
              resultWithPaymentId(
                  Map.of("payment_id", pending.paymentId()), Map.of("message", ex.detail())),
              "timeline",
              List.of(
                  AuditExecutionClient.timelineStep(
                      verb, action + " denied by payment-service.", "deny", nowIso()))));
      return SkillRunResult.terminal(
          "**" + label(verb) + " denied** — " + ex.detail() + "\n\nNothing was persisted.",
          activities,
          "skill." + skill + "." + verb + "_denied",
          skill);
    } catch (PaymentClientException ex) {
      activities.add(action + " failed: " + ex.getMessage());
      patchAudit(
          auditClient,
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "FAILED",
              "outcome",
              "error",
              "result",
              resultWithPaymentId(
                  Map.of("payment_id", pending.paymentId()), Map.of("message", ex.getMessage())),
              "timeline",
              List.of(
                  AuditExecutionClient.timelineStep(
                      verb, action + " failed: " + ex.getMessage(), "error", nowIso()))));
      return SkillRunResult.terminal(
          "**" + label(verb) + " failed** — " + ex.getMessage(),
          activities,
          "skill." + skill + "." + verb + "_error",
          skill);
    }

    String paymentId =
        SkillFormat.firstNonBlank(SkillFormat.str(payment.get("payment_id")), pending.paymentId());
    activities.add(
        mutation.successVerb()
            + " payment `"
            + paymentId
            + "` (status "
            + mutation.successStatus()
            + ").");
    // Linking to security_event_id happens in payment-service via X-Audit-Execution-Id.
    patchAudit(
        auditClient,
        pending.auditExecutionId(),
        subject,
        Map.of(
            "status",
            "COMPLETED",
            "outcome",
            "allow",
            "result",
            Map.of(
                "payment_id",
                paymentId,
                "status",
                mutation.successStatus(),
                "security_event_id",
                SkillFormat.str(payment.get("security_event_id"))),
            "timeline",
            List.of(
                AuditExecutionClient.timelineStep(
                    verb,
                    mutation.successVerb() + " payment `" + paymentId + "`.",
                    "allow",
                    nowIso()))));
    return SkillRunResult.terminal(
        mutation.successReport(payment, pending, subject),
        activities,
        "skill." + skill + "." + mutation.successStatus().toLowerCase(Locale.ROOT),
        skill);
  }

  static void persistForbiddenAudit(
      AuditExecutionClient auditClient,
      String skill,
      String action,
      Subject subject,
      String intentId,
      String message) {
    persistTerminalAudit(
        auditClient,
        skill,
        action,
        subject,
        Map.of(),
        "DENIED",
        "deny",
        intentId,
        List.of(
            AuditExecutionClient.timelineStep(
                "capability", message, "deny", nowIso())),
        Map.of(),
        null,
        Map.of("message", message));
  }

  private static String persistAwaitingAudit(
      AuditExecutionClient auditClient,
      String skill,
      String action,
      Subject subject,
      Map<String, Object> request,
      List<Map<String, Object>> timeline,
      Map<String, Object> timingsMs,
      Map<String, Object> policyExchange) {
    if (auditClient == null) {
      return null;
    }
    Map<String, Object> body = baseAuditBody(skill, action, request, "AWAITING_CONFIRMATION", "allow");
    body.put("interpretation", Map.of("intent_id", "skill." + skill + ".awaiting_confirmation"));
    body.put("timeline", timeline);
    body.put("timings_ms", timingsMs);
    body.put("governance", Map.of("policy_exchange", policyExchange));
    body.put(
        "result",
        resultWithPaymentId(request, Map.of("message", "awaiting Go / No Go")));
    return auditClient.create(body, subject);
  }

  private static void persistTerminalAudit(
      AuditExecutionClient auditClient,
      String skill,
      String action,
      Subject subject,
      Map<String, Object> request,
      String status,
      String outcome,
      String intentId,
      List<Map<String, Object>> timeline,
      Map<String, Object> timingsMs,
      Map<String, Object> policyExchange,
      Map<String, Object> result) {
    if (auditClient == null) {
      return;
    }
    Map<String, Object> body = baseAuditBody(skill, action, request, status, outcome);
    body.put("interpretation", Map.of("intent_id", intentId));
    body.put("timeline", timeline == null ? List.of() : timeline);
    body.put("timings_ms", timingsMs == null ? Map.of() : timingsMs);
    body.put("result", resultWithPaymentId(request, result));
    if (policyExchange != null) {
      body.put("governance", Map.of("policy_exchange", policyExchange));
    }
    auditClient.create(body, subject);
  }

  /** Prefer explicit result.payment_id; otherwise copy from request for list/detail columns. */
  static Map<String, Object> resultWithPaymentId(
      Map<String, Object> request, Map<String, Object> result) {
    Map<String, Object> out = new LinkedHashMap<>();
    if (result != null) {
      out.putAll(result);
    }
    Object existing = out.get("payment_id");
    if (existing != null && !String.valueOf(existing).isBlank()) {
      return out;
    }
    Object fromRequest = request == null ? null : request.get("payment_id");
    if (fromRequest != null && !String.valueOf(fromRequest).isBlank()) {
      out.put("payment_id", fromRequest);
    }
    return out;
  }

  private static void patchAudit(
      AuditExecutionClient auditClient,
      String executionId,
      Subject subject,
      Map<String, Object> patch) {
    if (auditClient == null || executionId == null || executionId.isBlank()) {
      return;
    }
    auditClient.patch(executionId, patch, subject);
  }

  private static Map<String, Object> baseAuditBody(
      String skill,
      String action,
      Map<String, Object> request,
      String status,
      String outcome) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("capability", capabilityFor(skill));
    body.put("skill", skill);
    body.put("channel", "chat");
    body.put("status", status);
    body.put("outcome", outcome);
    body.put("request", request == null ? Map.of() : request);
    body.put("interpretation", Map.of("action", action));
    return body;
  }

  static String capabilityFor(String skill) {
    return switch (skill) {
      case "submit_payment" -> "SUBMIT_PAYMENT";
      case "approve_payment" -> "APPROVE_PAYMENT";
      case "cancel_payment" -> "CANCEL_PAYMENT";
      case "create_payment" -> "CREATE_PAYMENT";
      default -> skill == null ? "UNKNOWN" : skill.toUpperCase(Locale.ROOT);
    };
  }

  private static Map<String, Object> requestFromPayment(Map<String, Object> payment) {
    Map<String, Object> request = new LinkedHashMap<>();
    request.put("payment_id", payment.get("payment_id"));
    request.put("instruction_id", payment.get("instruction_id"));
    request.put("amount", payment.get("amount"));
    request.put("currency", payment.get("currency"));
    request.put("status", payment.get("status"));
    request.put("owning_lob", payment.get("owning_lob"));
    request.put("value_date", payment.get("value_date"));
    return request;
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
    return verb.substring(0, 1).toUpperCase(Locale.ROOT) + verb.substring(1);
  }

  private static String nowIso() {
    return Instant.now().toString();
  }

  private static boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
