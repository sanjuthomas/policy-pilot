package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.formatting.AnswerRenderer;
import java.util.Map;
import org.springframework.stereotype.Component;

/** Maps eligibility API JSON → view models; answer prose is Thymeleaf. */
@Component
public class EligibilityAnswerFormatter {

  private static final String PAYMENT_APPROVERS_TEMPLATE = "eligible-payment-approvers";
  private static final String PAYMENT_SUBMITTERS_TEMPLATE = "eligible-payment-submitters";
  private static final String INSTRUCTION_APPROVERS_TEMPLATE = "eligible-instruction-approvers";

  private final AnswerRenderer answerRenderer;

  public EligibilityAnswerFormatter(AnswerRenderer answerRenderer) {
    this.answerRenderer = answerRenderer;
  }

  public String formatEligiblePaymentApproversAnswer(Map<String, Object> data) {
    return answerRenderer.render(PAYMENT_APPROVERS_TEMPLATE, toPaymentApproversView(data));
  }

  public String formatEligiblePaymentSubmittersAnswer(Map<String, Object> data) {
    return answerRenderer.render(PAYMENT_SUBMITTERS_TEMPLATE, toPaymentSubmittersView(data));
  }

  public String formatEligibleInstructionApproversAnswer(Map<String, Object> data) {
    return answerRenderer.render(INSTRUCTION_APPROVERS_TEMPLATE, toInstructionApproversView(data));
  }

  static EligiblePaymentApproversView toPaymentApproversView(Map<String, Object> data) {
    return new EligiblePaymentApproversView(
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("payment_id"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("payment_status"))),
        data.get("amount"),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("currency"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("owning_lob"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_id"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_status"))),
        EligibilityPayloads.blockedOrNull(data.get("approval_blocked_reason")),
        EligibilityPayloads.toApproverRows(data.get("eligible")),
        EligibilityPayloads.toApproverRows(data.get("prospective_eligible")),
        EligibilityPayloads.parseCandidatesEvaluated(data.get("candidates_evaluated")));
  }

  static EligiblePaymentSubmittersView toPaymentSubmittersView(Map<String, Object> data) {
    return new EligiblePaymentSubmittersView(
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("payment_id"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("payment_status"))),
        data.get("amount"),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("currency"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("owning_lob"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_id"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_status"))),
        EligibilityPayloads.blockedOrNull(data.get("submit_blocked_reason")),
        EligibilityPayloads.toApproverRows(data.get("eligible")),
        EligibilityPayloads.parseCandidatesEvaluated(data.get("candidates_evaluated")));
  }

  static EligibleInstructionApproversView toInstructionApproversView(Map<String, Object> data) {
    return new EligibleInstructionApproversView(
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_id"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_status"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("instruction_type"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("owning_lob"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("created_by_user_id"))),
        EligibilityPayloads.blankToNull(EligibilityPayloads.str(data.get("created_by_title"))),
        EligibilityPayloads.blockedOrNull(data.get("approval_blocked_reason")),
        EligibilityPayloads.toApproverRows(data.get("eligible")),
        EligibilityPayloads.toApproverRows(data.get("prospective_eligible")),
        EligibilityPayloads.parseCandidatesEvaluated(data.get("candidates_evaluated")));
  }
}
