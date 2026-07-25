package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.AuthzEvaluateException;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.EvaluateExchange;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentClientException;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentDeniedException;
import com.sanjuthomas.policypilot.skill.SkillSlots.CreateParams;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/** Create-payment skill: role gate → dry-run CREATE → confirmation card → Go/No Go create. */
@Component
public class CreatePaymentSkill {

  private static final Logger log = LoggerFactory.getLogger(CreatePaymentSkill.class);
  static final String SKILL = "create_payment";

  private final EligibilityClient eligibilityClient;
  private final AuthzPaymentEvaluateClient authzClient;
  private final PaymentMutationClient paymentClient;
  private final AuditExecutionClient auditClient;
  private final PendingSkillStore store;

  public CreatePaymentSkill(
      EligibilityClient eligibilityClient,
      AuthzPaymentEvaluateClient authzClient,
      PaymentMutationClient paymentClient,
      AuditExecutionClient auditClient,
      PendingSkillStore store) {
    this.eligibilityClient = eligibilityClient;
    this.authzClient = authzClient;
    this.paymentClient = paymentClient;
    this.auditClient = auditClient;
    this.store = store;
  }

  public SkillRunResult phase1(CreateParams params, Subject subject) {
    long started = System.currentTimeMillis();
    List<String> activities = new ArrayList<>();
    List<Map<String, Object>> timeline = new ArrayList<>();
    timeline.add(
        AuditExecutionClient.timelineStep(
            "identity",
            "Subject `" + subject.userId() + "` established for create-payment skill.",
            null,
            nowIso()));

    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    if (!caps.canCreatePayment()) {
      activities.add("Checked role — `" + subject.userId() + "` does not hold `PAYMENT_CREATOR`.");
      timeline.add(
          AuditExecutionClient.timelineStep(
              "capability",
              "Role gate denied — missing PAYMENT_CREATOR.",
              "deny",
              nowIso()));
      persistTerminalAudit(
          subject,
          params,
          "DENIED",
          "deny",
          "skill.create_payment.forbidden",
          timeline,
          Map.of("total", System.currentTimeMillis() - started),
          null,
          Map.of("message", "missing PAYMENT_CREATOR"));
      return SkillRunResult.terminal(
          "**No Go from preflight** — `"
              + subject.userId()
              + "` cannot run the create-payment skill (needs `PAYMENT_CREATOR`).\n\n"
              + "No payment was created.",
          activities,
          "skill.create_payment.forbidden",
          SKILL);
    }

    if (isBlank(subject.bearerToken())) {
      return SkillRunResult.terminal(
          "Sign-in token missing — cannot load the instruction or evaluate policy.",
          List.of("Missing user session token."),
          "skill.create_payment.auth_error",
          SKILL);
    }

    activities.add(
        "Parsed request: instruction `"
            + params.instructionId()
            + "`, amount **"
            + String.format(java.util.Locale.US, "%,.0f", params.amount())
            + "**, value date **"
            + params.valueDate()
            + "**.");
    timeline.add(
        AuditExecutionClient.timelineStep(
            "request",
            "Parsed create-payment slots for instruction `" + params.instructionId() + "`.",
            null,
            nowIso()));

    Map<String, Object> instruction;
    long instructionStarted = System.currentTimeMillis();
    try {
      instruction =
          eligibilityClient.getInstruction(
              params.instructionId(), subject.bearerToken(), subject.sessionId());
    } catch (ResponseStatusException ex) {
      if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
        timeline.add(
            AuditExecutionClient.timelineStep(
                "instruction", "Instruction not found.", "deny", nowIso()));
        persistTerminalAudit(
            subject,
            params,
            "FAILED",
            "error",
            "skill.create_payment.instruction_missing",
            timeline,
            Map.of(
                "instruction_get",
                System.currentTimeMillis() - instructionStarted,
                "total",
                System.currentTimeMillis() - started),
            null,
            Map.of("message", "instruction not found"));
        return SkillRunResult.terminal(
            "**Stopped** — instruction `"
                + params.instructionId()
                + "` was not found. No payment was created.",
            activities,
            "skill.create_payment.instruction_missing",
            SKILL);
      }
      if (ex.getStatusCode() == HttpStatus.FORBIDDEN) {
        timeline.add(
            AuditExecutionClient.timelineStep(
                "instruction", "Instruction VIEW denied.", "deny", nowIso()));
        persistTerminalAudit(
            subject,
            params,
            "DENIED",
            "deny",
            "skill.create_payment.instruction_forbidden",
            timeline,
            Map.of(
                "instruction_get",
                System.currentTimeMillis() - instructionStarted,
                "total",
                System.currentTimeMillis() - started),
            null,
            Map.of("message", "instruction forbidden"));
        return SkillRunResult.terminal(
            "**Stopped** — you are not authorized to access instruction `"
                + params.instructionId()
                + "` (covering LOB / VIEW entitlement). No payment was created.",
            activities,
            "skill.create_payment.instruction_forbidden",
            SKILL);
      }
      return SkillRunResult.terminal(
          "**Stopped** — could not load the instruction ("
              + ex.getReason()
              + "). No payment was created.",
          activities,
          "skill.create_payment.instruction_error",
          SKILL);
    }
    long instructionMs = System.currentTimeMillis() - instructionStarted;

    String owningLob = SkillFormat.firstNonBlank(SkillFormat.str(instruction.get("owning_lob")), "—");
    String currency = SkillFormat.str(instruction.get("currency"));
    String status = SkillFormat.str(instruction.get("status"));
    String endDate = SkillFormat.str(instruction.get("end_date"));
    int instructionVersion = SkillFormat.asInt(instruction.get("version_number"), 1);
    activities.add(
        "Loaded instruction `"
            + params.instructionId()
            + "` — LOB **"
            + owningLob
            + "**, status **"
            + status
            + "**, currency **"
            + currency
            + "**.");
    timeline.add(
        AuditExecutionClient.timelineStep(
            "instruction",
            "Loaded instruction `" + params.instructionId() + "` (" + status + ").",
            null,
            nowIso()));

    Map<String, Object> payload =
        syntheticPayload(params, instruction, subject, status, endDate, owningLob, instructionVersion, currency);
    EvaluateExchange exchange;
    long evaluateStarted = System.currentTimeMillis();
    try {
      exchange = authzClient.evaluateExchange("CREATE", payload, status, endDate, subject);
    } catch (AuthzEvaluateException ex) {
      timeline.add(
          AuditExecutionClient.timelineStep(
              "preflight_opa", "CREATE evaluate failed: " + ex.getMessage(), "error", nowIso()));
      persistTerminalAudit(
          subject,
          params,
          "FAILED",
          "error",
          "skill.create_payment.evaluate_error",
          timeline,
          Map.of(
              "instruction_get",
              instructionMs,
              "preflight_evaluate",
              System.currentTimeMillis() - evaluateStarted,
              "total",
              System.currentTimeMillis() - started),
          null,
          Map.of("message", ex.getMessage()));
      return SkillRunResult.terminal(
          "**Stopped** — could not evaluate CREATE permission (" + ex.getMessage() + ").",
          activities,
          "skill.create_payment.evaluate_error",
          SKILL);
    }
    long evaluateMs = System.currentTimeMillis() - evaluateStarted;
    PolicyDecision decision = exchange.decision();

    if (!decision.allowed()) {
      activities.add("**Denied** — " + SkillFormat.violations(decision.violations()));
      timeline.add(
          AuditExecutionClient.timelineStep(
              "preflight_opa",
              "CREATE denied: " + SkillFormat.violations(decision.violations()),
              "deny",
              nowIso()));
      persistTerminalAudit(
          subject,
          params,
          "DENIED",
          "deny",
          "skill.create_payment.denied",
          timeline,
          Map.of(
              "instruction_get",
              instructionMs,
              "preflight_evaluate",
              evaluateMs,
              "total",
              System.currentTimeMillis() - started),
          AuditExecutionClient.policyExchange(exchange.request(), exchange.response()),
          Map.of("message", "CREATE denied", "violations", decision.violations()));
      return SkillRunResult.terminal(
          "**No** — `"
              + subject.userId()
              + "` may not create this payment under policy.\n\nViolations: "
              + SkillFormat.violations(decision.violations())
              + "\n\nNo payment was created.",
          activities,
          "skill.create_payment.denied",
          SKILL);
    }

    activities.add(
        "**Yes** — `"
            + subject.userId()
            + "` ("
            + SkillFormat.displayName(subject)
            + ") may create this draft. Basis: "
            + SkillFormat.basis(decision.allowBasis(), "CREATE allowed"));
    timeline.add(
        AuditExecutionClient.timelineStep(
            "preflight_opa",
            "CREATE allowed. Basis: " + SkillFormat.basis(decision.allowBasis(), "CREATE allowed"),
            "allow",
            nowIso()));

    ConfirmationCard card =
        SkillFormat.cardFromInstruction(instruction, params.amount(), params.valueDate(), null, null);
    String auditExecutionId =
        persistAwaitingAudit(
            subject,
            params,
            currency,
            timeline,
            Map.of(
                "instruction_get",
                instructionMs,
                "preflight_evaluate",
                evaluateMs,
                "total",
                System.currentTimeMillis() - started),
            AuditExecutionClient.policyExchange(exchange.request(), exchange.response()));

    PendingSkill pending =
        new PendingSkill(
            store.newPendingId(),
            SKILL,
            subject.userId(),
            null,
            params.instructionId(),
            params.amount(),
            params.valueDate(),
            currency,
            owningLob,
            null,
            status,
            endDate,
            SkillFormat.str(instruction.get("instruction_type")),
            instructionVersion,
            null,
            null,
            card,
            store.defaultExpiresAt(),
            auditExecutionId);
    store.put(pending);

    return SkillRunResult.awaiting(
        "Preflight passed. Review the payment details below, then choose "
            + "**Go** to create the draft or **No Go** to cancel.",
        activities,
        pending.pendingId(),
        card,
        "skill.create_payment.awaiting_confirmation",
        SKILL);
  }

  public SkillRunResult confirm(String pendingId, String decision, Subject subject) {
    long started = System.currentTimeMillis();
    PendingSkill pending = store.get(pendingId);
    if (pending == null || !SKILL.equals(pending.skill())) {
      return SkillRunResult.terminal(
          "That confirmation expired or was already used. "
              + "Ask again to create the payment if you still need it.",
          List.of("Pending skill not found or expired."),
          "skill.create_payment.pending_missing",
          SKILL);
    }
    if (!pending.userId().equals(subject.userId())) {
      return SkillRunResult.terminal(
          "This confirmation belongs to another user. No payment was created.",
          List.of("Pending skill user mismatch."),
          "skill.create_payment.pending_forbidden",
          SKILL);
    }
    if ("no_go".equals(decision)) {
      store.pop(pendingId);
      patchAudit(
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "CANCELLED",
              "outcome",
              "cancelled",
              "result",
              Map.of("message", "user selected No Go"),
              "timeline",
              List.of(
                  AuditExecutionClient.timelineStep(
                      "confirmation", "User selected No Go.", "cancelled", nowIso()))));
      return SkillRunResult.terminal(
          "**No Go** — cancelled. No payment was created.",
          List.of("User selected No Go — pending create discarded."),
          "skill.create_payment.cancelled",
          SKILL);
    }
    if (!"go".equals(decision)) {
      return SkillRunResult.terminal(
          "Decision must be `\"go\"` or `\"no_go\"`.",
          List.of("Invalid decision: " + decision),
          "skill.create_payment.bad_decision",
          SKILL);
    }
    if (isBlank(subject.bearerToken())) {
      return SkillRunResult.terminal(
          "Sign-in token missing — cannot create the payment.",
          List.of("Missing user session token on confirm."),
          "skill.create_payment.auth_error",
          SKILL);
    }

    pending = store.pop(pendingId);
    if (pending == null) {
      return SkillRunResult.terminal(
          "That confirmation was already used. No additional payment was created.",
          List.of("Pending skill already consumed."),
          "skill.create_payment.pending_missing",
          SKILL);
    }

    List<String> activities = new ArrayList<>();
    activities.add(
        "Go selected — creating draft payment for instruction `" + pending.instructionId() + "`…");

    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("payment_id", "SKILL-PREFLIGHT");
    payload.put("instruction_id", pending.instructionId());
    payload.put("instruction_version", pending.instructionVersion());
    payload.put("status", "DRAFT");
    payload.put("amount", pending.amount());
    payload.put("currency", pending.currency());
    payload.put("instruction_status", pending.instructionStatus());
    payload.put("instruction_end_date", pending.instructionEndDate());
    payload.put("instruction_type", pending.instructionType());
    payload.put("instruction_owning_lob", pending.owningLob());
    payload.put("created_by", createdBy(subject));
    try {
      EvaluateExchange recheck =
          authzClient.evaluateExchange(
              "CREATE", payload, pending.instructionStatus(), pending.instructionEndDate(), subject);
      if (!recheck.decision().allowed()) {
        activities.add(
            "Re-check denied CREATE: " + SkillFormat.violations(recheck.decision().violations()));
        patchAudit(
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
                Map.of(
                    "message",
                    "recheck denied",
                    "violations",
                    recheck.decision().violations()),
                "timings_ms",
                Map.of("total", System.currentTimeMillis() - started)));
        return SkillRunResult.terminal(
            "**Stopped before create** — policy no longer allows CREATE ("
                + SkillFormat.violations(recheck.decision().violations())
                + "). No payment was created.",
            activities,
            "skill.create_payment.recheck_denied",
            SKILL);
      }
    } catch (AuthzEvaluateException ex) {
      log.warn("create-payment confirm recheck failed: {} — aborting create", ex.toString());
      activities.add("Could not re-check policy (" + ex.getMessage() + ") — stopped before create.");
      return SkillRunResult.terminal(
          "**Stopped before create** — could not re-check CREATE permission ("
              + ex.getMessage()
              + "). No payment was created.",
          activities,
          "skill.create_payment.recheck_error",
          SKILL);
    }

    Map<String, Object> payment;
    long createStarted = System.currentTimeMillis();
    try {
      payment =
          paymentClient.createPayment(
              pending.instructionId(),
              pending.amount(),
              pending.valueDate(),
              subject.bearerToken(),
              subject.sessionId(),
              pending.auditExecutionId());
    } catch (PaymentDeniedException ex) {
      activities.add("CREATE denied by payment-service: " + ex.detail());
      patchAudit(
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "DENIED",
              "outcome",
              "deny",
              "result",
              Map.of("message", ex.detail()),
              "timings_ms",
              Map.of(
                  "create",
                  System.currentTimeMillis() - createStarted,
                  "total",
                  System.currentTimeMillis() - started)));
      return SkillRunResult.terminal(
          "**Create denied** — " + ex.detail() + "\n\nNo payment was persisted.",
          activities,
          "skill.create_payment.create_denied",
          SKILL);
    } catch (PaymentClientException ex) {
      activities.add("CREATE failed: " + ex.getMessage());
      patchAudit(
          pending.auditExecutionId(),
          subject,
          Map.of(
              "status",
              "FAILED",
              "outcome",
              "error",
              "result",
              Map.of("message", ex.getMessage()),
              "timings_ms",
              Map.of(
                  "create",
                  System.currentTimeMillis() - createStarted,
                  "total",
                  System.currentTimeMillis() - started)));
      return SkillRunResult.terminal(
          "**Create failed** — " + ex.getMessage(),
          activities,
          "skill.create_payment.create_error",
          SKILL);
    }

    activities.add("Created draft payment `" + SkillFormat.str(payment.get("payment_id")) + "`.");
    // Linking to security_event_id happens in payment-service via X-Audit-Execution-Id.
    patchAudit(
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
                SkillFormat.str(payment.get("payment_id")),
                "security_event_id",
                SkillFormat.str(payment.get("security_event_id"))),
            "timings_ms",
            Map.of(
                "create",
                System.currentTimeMillis() - createStarted,
                "total",
                System.currentTimeMillis() - started),
            "timeline",
            List.of(
                AuditExecutionClient.timelineStep(
                    "create",
                    "Draft payment `" + SkillFormat.str(payment.get("payment_id")) + "` created.",
                    "allow",
                    nowIso()))));
    return SkillRunResult.terminal(
        SkillFormat.createdReport(payment, pending.card()),
        activities,
        "skill.create_payment.created",
        SKILL);
  }

  private String persistAwaitingAudit(
      Subject subject,
      CreateParams params,
      String currency,
      List<Map<String, Object>> timeline,
      Map<String, Object> timingsMs,
      Map<String, Object> policyExchange) {
    if (auditClient == null) {
      return null;
    }
    Map<String, Object> body = baseAuditBody(params, currency, "AWAITING_CONFIRMATION", "allow");
    body.put("interpretation", Map.of("intent_id", "skill.create_payment.awaiting_confirmation"));
    body.put("timeline", timeline);
    body.put("timings_ms", timingsMs);
    body.put("governance", Map.of("policy_exchange", policyExchange));
    body.put("result", Map.of("message", "awaiting Go / No Go"));
    return auditClient.create(body, subject);
  }

  private void persistTerminalAudit(
      Subject subject,
      CreateParams params,
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
    Map<String, Object> body = baseAuditBody(params, null, status, outcome);
    body.put("interpretation", Map.of("intent_id", intentId));
    body.put("timeline", timeline);
    body.put("timings_ms", timingsMs);
    body.put("result", result == null ? Map.of() : result);
    if (policyExchange != null) {
      body.put("governance", Map.of("policy_exchange", policyExchange));
    }
    auditClient.create(body, subject);
  }

  private void patchAudit(String executionId, Subject subject, Map<String, Object> patch) {
    if (auditClient == null || executionId == null || executionId.isBlank()) {
      return;
    }
    auditClient.patch(executionId, patch, subject);
  }

  private static Map<String, Object> baseAuditBody(
      CreateParams params, String currency, String status, String outcome) {
    Map<String, Object> request = new LinkedHashMap<>();
    request.put("instruction_id", params.instructionId());
    request.put("amount", params.amount());
    request.put("value_date", params.valueDate());
    if (currency != null) {
      request.put("currency", currency);
    }
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("capability", "CREATE_PAYMENT");
    body.put("skill", SKILL);
    body.put("channel", "chat");
    body.put("status", status);
    body.put("outcome", outcome);
    body.put("request", request);
    return body;
  }

  private static Map<String, Object> syntheticPayload(
      CreateParams params,
      Map<String, Object> instruction,
      Subject subject,
      String status,
      String endDate,
      String owningLob,
      int instructionVersion,
      String currency) {
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("payment_id", "SKILL-PREFLIGHT");
    payload.put("instruction_id", params.instructionId());
    payload.put("instruction_version", instructionVersion);
    payload.put("status", "DRAFT");
    payload.put("amount", params.amount());
    payload.put("currency", currency);
    payload.put("instruction_status", status);
    payload.put("instruction_end_date", endDate);
    payload.put("instruction_type", SkillFormat.str(instruction.get("instruction_type")));
    payload.put("instruction_owning_lob", owningLob);
    payload.put("created_by", createdBy(subject));
    return payload;
  }

  private static Map<String, Object> createdBy(Subject subject) {
    Map<String, Object> createdBy = new LinkedHashMap<>();
    createdBy.put("user_id", subject.userId());
    createdBy.put("supervisor_id", subject.supervisorId());
    return createdBy;
  }

  private static String nowIso() {
    return Instant.now().toString();
  }

  private static boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
