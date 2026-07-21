package com.sanjuthomas.policypilot.policysummary;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/** Policy-summary path: normative OPA summary via authz. */
@Service
public class PolicySummaryService {

  private final EligibilityClient eligibilityClient;
  private final PolicySummaryAnswerFormatter answerFormatter;

  public PolicySummaryService(
      EligibilityClient eligibilityClient, PolicySummaryAnswerFormatter answerFormatter) {
    this.eligibilityClient = eligibilityClient;
    this.answerFormatter = answerFormatter;
  }

  public LaneAnswer answer(Subject subject, RouterDecision decision) {
    String domain =
        decision != null && StringUtils.hasText(decision.getPolicyDomain())
            ? decision.getPolicyDomain().strip().toLowerCase()
            : "payment";
    String action =
        decision != null && StringUtils.hasText(decision.getPolicyAction())
            ? decision.getPolicyAction().strip().toUpperCase()
            : "APPROVE";
    Map<String, Object> data =
        eligibilityClient.policySummary(
            domain, action, subject.bearerToken(), subject.sessionId());
    return LaneAnswer.of(
        answerFormatter.format(data), "policy_summary", "eligibility_api");
  }
}
