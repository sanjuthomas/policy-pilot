package com.sanjuthomas.policypilot.person;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * {@code path=person_permissions}: ZITADEL directory permission summary via authz (not live OPA).
 */
@Service
public class PersonPermissionSummaryService {

  private final EligibilityClient eligibilityClient;
  private final PersonPermissionSummaryAnswerFormatter answerFormatter;

  public PersonPermissionSummaryService(
      EligibilityClient eligibilityClient,
      PersonPermissionSummaryAnswerFormatter answerFormatter) {
    this.eligibilityClient = eligibilityClient;
    this.answerFormatter = answerFormatter;
  }

  public LaneAnswer answer(Subject subject, RouterDecision decision) {
    String query =
        decision != null && StringUtils.hasText(decision.getPersonQuery())
            ? decision.getPersonQuery().strip()
            : null;
    if (!StringUtils.hasText(query)) {
      return LaneAnswer.of(
          "Ask again with a user id (e.g. `pay-203`) or a `Family, Given` display name.",
          "person_permissions",
          "eligibility_api");
    }
    Map<String, Object> data =
        eligibilityClient.personPermissionSummary(
            query, subject.bearerToken(), subject.sessionId());
    return LaneAnswer.of(
        answerFormatter.format(data), "person_permissions", "eligibility_api");
  }
}
