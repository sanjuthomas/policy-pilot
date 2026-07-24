package com.sanjuthomas.policypilot.skill;

import com.sanjuthomas.policypilot.auth.ChatCapabilities;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.skill.SkillSlots.CreateParams;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Payment mutation skill lane: mode gate + capability fence, then dispatch to the create / submit /
 * approve / cancel runners. Mirrors the Python skill handler + {@code gates.py} lane access.
 */
@Component
public class PaymentSkillService {

  private static final Set<String> SKILL_MODES = Set.of("payments", "all");

  private final CreatePaymentSkill createSkill;
  private final SubmitPaymentSkill submitSkill;
  private final ApprovePaymentSkill approveSkill;
  private final CancelPaymentSkill cancelSkill;

  public PaymentSkillService(
      CreatePaymentSkill createSkill,
      SubmitPaymentSkill submitSkill,
      ApprovePaymentSkill approveSkill,
      CancelPaymentSkill cancelSkill) {
    this.createSkill = createSkill;
    this.submitSkill = submitSkill;
    this.approveSkill = approveSkill;
    this.cancelSkill = cancelSkill;
  }

  public SkillRunResult phase1(RouterDecision decision, String message, String mode, Subject subject) {
    String skill = resolveSkill(decision);

    String resolvedMode = mode == null ? "" : mode.strip().toLowerCase(java.util.Locale.ROOT);
    if (!SKILL_MODES.contains(resolvedMode)) {
      return SkillRunResult.terminal(
          "Payment mutation skills are available in **Payments** mode. "
              + "Switch modes and ask again (create / submit / approve with the required ids).",
          List.of("Skill lane requires Payments (or All) mode."),
          "gate.skill_wrong_mode",
          skill);
    }

    ChatCapabilities caps = ChatCapabilities.forSubject(subject);
    if (!caps.operational()) {
      return SkillRunResult.terminal(
          "Payment mutation skills require **PAYMENT_CREATOR** (create/submit) or "
              + "**FUNDING_APPROVER** (approve). Sign in as an operational payment user or switch "
              + "to Events / Instructions to investigate.",
          List.of("Skill lane requires an operational payment role."),
          "gate.skill_not_creator",
          skill);
    }

    return switch (skill) {
      case "submit_payment" ->
          dispatchPaymentId(
              skill,
              decision,
              message,
              subject,
              submitSkill::phase1,
              "I understood you want to submit a payment for approval, but I need a payment id "
                  + "(e.g. `20260715-FICC-P-9`).");
      case "approve_payment" ->
          dispatchPaymentId(
              skill,
              decision,
              message,
              subject,
              approveSkill::phase1,
              "I understood you want to approve a payment, but I need a payment id "
                  + "(e.g. `20260715-FICC-P-9`).");
      case "cancel_payment" ->
          dispatchPaymentId(
              skill,
              decision,
              message,
              subject,
              cancelSkill::phase1,
              "I understood you want to cancel a payment, but I need a payment id "
                  + "(e.g. `20260715-FICC-P-9`).");
      default -> dispatchCreate(decision, message, subject);
    };
  }

  public SkillRunResult confirm(String skill, String pendingId, String decision, Subject subject) {
    return switch (normalizeSkill(skill)) {
      case "submit_payment" -> submitSkill.confirm(pendingId, decision, subject);
      case "approve_payment" -> approveSkill.confirm(pendingId, decision, subject);
      case "cancel_payment" -> cancelSkill.confirm(pendingId, decision, subject);
      default -> createSkill.confirm(pendingId, decision, subject);
    };
  }

  private SkillRunResult dispatchCreate(
      RouterDecision decision, String message, Subject subject) {
    Optional<CreateParams> params = SkillSlots.resolveCreate(decision, message);
    if (params.isEmpty()) {
      return SkillRunResult.terminal(
          "I understood you want to create a payment, but I need an instruction id, amount, and "
              + "value date (e.g. today/tomorrow or YYYY-MM-DD).",
          List.of("Incomplete create-payment slots."),
          "skill.create_payment.incomplete",
          "create_payment");
    }
    return createSkill.phase1(params.get(), subject);
  }

  private interface PaymentIdPhase1 {
    SkillRunResult run(String paymentId, Subject subject);
  }

  private SkillRunResult dispatchPaymentId(
      String skill,
      RouterDecision decision,
      String message,
      Subject subject,
      PaymentIdPhase1 runner,
      String incompleteMessage) {
    Optional<String> paymentId = SkillSlots.resolvePaymentId(decision, message);
    if (paymentId.isEmpty()) {
      return SkillRunResult.terminal(
          incompleteMessage,
          List.of("Incomplete " + skill + " slots."),
          "skill." + skill + ".incomplete",
          skill);
    }
    return runner.run(paymentId.get(), subject);
  }

  private static String resolveSkill(RouterDecision decision) {
    String skill = decision == null ? null : decision.getSkill();
    return normalizeSkill(skill);
  }

  private static String normalizeSkill(String skill) {
    if (skill == null || skill.isBlank()) {
      return "create_payment";
    }
    return switch (skill.strip().toLowerCase(java.util.Locale.ROOT)) {
      case "submit_payment" -> "submit_payment";
      case "approve_payment" -> "approve_payment";
      case "cancel_payment" -> "cancel_payment";
      default -> "create_payment";
    };
  }
}
