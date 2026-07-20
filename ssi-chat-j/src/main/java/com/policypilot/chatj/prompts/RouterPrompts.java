package com.policypilot.chatj.prompts;

/** System prompts for LLM calls. Grow the router prompt as new paths are implemented. */
public final class RouterPrompts {

  private RouterPrompts() {}

  public static final String ROUTER_SYSTEM =
      """
      You are the Policy Pilot chat intent router.
      Return ONLY a RouterDecision JSON object.
      For questions like "Who can approve payment PAY-...?" set:
        path=eligibility, eligibilityTarget=payment, eligibilityAction=APPROVE.
      Prefer eligibility over neo4j_direct for live OPA approver/submitter questions.
      """;
}
