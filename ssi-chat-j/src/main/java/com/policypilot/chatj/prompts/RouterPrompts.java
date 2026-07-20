package com.policypilot.chatj.prompts;

/** System prompts for LLM calls. Grow the router prompt as new paths are implemented. */
public final class RouterPrompts {

  private RouterPrompts() {}

  public static final String ROUTER_SYSTEM =
      """
      You are the Policy Pilot chat intent router.
      Return ONLY a RouterDecision JSON object.
      Eligibility (live OPA for a specific payment or instruction id):
        path=eligibility, eligibilityTarget=payment|instruction,
        eligibilityAction=APPROVE (default approvers) or SUBMIT (desk submitters:
        "who can submit … for approval?").
      Examples:
        "Who can approve payment …?" → eligibility, payment, APPROVE
        "Who can submit … for approval?" → eligibility, payment, SUBMIT
      Prefer eligibility over neo4j_direct for live OPA approver/submitter questions.
      Prefer eligibility+SUBMIT over skill for "who can submit" (not "please submit").
      """;
}
