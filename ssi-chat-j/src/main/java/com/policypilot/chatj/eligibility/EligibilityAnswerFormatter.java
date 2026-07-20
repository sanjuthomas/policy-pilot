package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.formatting.AnswerRenderer;
import java.util.Map;
import org.springframework.stereotype.Component;

/** Maps eligibility API JSON → view models; answer prose is Thymeleaf. */
@Component
public class EligibilityAnswerFormatter {

  private static final String APPROVERS_TEMPLATE = "eligible-approvers";
  private static final String SUBMITTERS_TEMPLATE = "eligible-submitters";

  private final AnswerRenderer answerRenderer;

  public EligibilityAnswerFormatter(AnswerRenderer answerRenderer) {
    this.answerRenderer = answerRenderer;
  }

  public String formatEligibleApproversAnswer(Map<String, Object> data) {
    return answerRenderer.render(APPROVERS_TEMPLATE, toApproversView(data));
  }

  public String formatEligibleSubmittersAnswer(Map<String, Object> data) {
    return answerRenderer.render(SUBMITTERS_TEMPLATE, toSubmittersView(data));
  }

  static EligibleApproversView toApproversView(Map<String, Object> data) {
    return new EligibleApproversView(
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

  static EligibleSubmittersView toSubmittersView(Map<String, Object> data) {
    return new EligibleSubmittersView(
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
}
