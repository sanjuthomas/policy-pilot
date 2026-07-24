package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.AuthzEvaluateException;
import com.sanjuthomas.policypilot.skill.AuthzPaymentEvaluateClient.PolicyDecision;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentClientException;
import com.sanjuthomas.policypilot.skill.PaymentMutationClient.PaymentDeniedException;
import com.sanjuthomas.policypilot.skill.SkillSlots.CreateParams;
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
  private final PendingSkillStore store;

  public CreatePaymentSkill(
      EligibilityClient eligibilityClient,
      AuthzPaymentEvaluateClient authzClient,
      PaymentMutationClient paymentClient,
      PendingSkillStore store) {
    this.eligibilityClient = eligibilityClient;
    this.authzClient = authzClient;
    this.paymentClient = paymentClient;
    this.store = store;
  }

  public SkillRunResult phase1(CreateParams params, Subject subject) {
    List<String> activities = new ArrayList<>();
    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    if (!caps.canCreatePayment()) {
      activities.add("Checked role — `" + subject.userId() + "` does not hold `PAYMENT_CREATOR`.");
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

    Map<String, Object> instruction;
    try {
      instruction =
          eligibilityClient.getInstruction(
              params.instructionId(), subject.bearerToken(), subject.sessionId());
    } catch (ResponseStatusException ex) {
      if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
        return SkillRunResult.terminal(
            "**Stopped** — instruction `"
                + params.instructionId()
                + "` was not found. No payment was created.",
            activities,
            "skill.create_payment.instruction_missing",
            SKILL);
      }
      if (ex.getStatusCode() == HttpStatus.FORBIDDEN) {
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

    Map<String, Object> payload =
        syntheticPayload(params, instruction, subject, status, endDate, owningLob, instructionVersion, currency);
    PolicyDecision decision;
    try {
      decision = authzClient.evaluate("CREATE", payload, status, endDate, subject);
    } catch (AuthzEvaluateException ex) {
      return SkillRunResult.terminal(
          "**Stopped** — could not evaluate CREATE permission (" + ex.getMessage() + ").",
          activities,
          "skill.create_payment.evaluate_error",
          SKILL);
    }

    if (!decision.allowed()) {
      activities.add("**Denied** — " + SkillFormat.violations(decision.violations()));
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

    ConfirmationCard card =
        SkillFormat.cardFromInstruction(instruction, params.amount(), params.valueDate(), null, null);
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
            store.defaultExpiresAt());
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
      PolicyDecision recheck =
          authzClient.evaluate(
              "CREATE", payload, pending.instructionStatus(), pending.instructionEndDate(), subject);
      if (!recheck.allowed()) {
        activities.add("Re-check denied CREATE: " + SkillFormat.violations(recheck.violations()));
        return SkillRunResult.terminal(
            "**Stopped before create** — policy no longer allows CREATE ("
                + SkillFormat.violations(recheck.violations())
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
    try {
      payment =
          paymentClient.createPayment(
              pending.instructionId(),
              pending.amount(),
              pending.valueDate(),
              subject.bearerToken(),
              subject.sessionId());
    } catch (PaymentDeniedException ex) {
      activities.add("CREATE denied by payment-service: " + ex.detail());
      return SkillRunResult.terminal(
          "**Create denied** — " + ex.detail() + "\n\nNo payment was persisted.",
          activities,
          "skill.create_payment.create_denied",
          SKILL);
    } catch (PaymentClientException ex) {
      activities.add("CREATE failed: " + ex.getMessage());
      return SkillRunResult.terminal(
          "**Create failed** — " + ex.getMessage(),
          activities,
          "skill.create_payment.create_error",
          SKILL);
    }

    activities.add("Created draft payment `" + SkillFormat.str(payment.get("payment_id")) + "`.");
    return SkillRunResult.terminal(
        SkillFormat.createdReport(payment, pending.card()),
        activities,
        "skill.create_payment.created",
        SKILL);
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

  private static boolean isBlank(String value) {
    return value == null || value.isBlank();
  }
}
