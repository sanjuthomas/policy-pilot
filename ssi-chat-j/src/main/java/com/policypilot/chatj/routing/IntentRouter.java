package com.policypilot.chatj.routing;

import com.policypilot.chatj.pipeline.RouterDecision;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

@Service
public class IntentRouter {

  private static final Logger log = LoggerFactory.getLogger(IntentRouter.class);

  private static final String ROUTER_SYSTEM =
      """
      You are the Policy Pilot chat intent router.
      Return ONLY a RouterDecision JSON object.
      For questions like "Who can approve payment PAY-...?" set:
        path=eligibility, eligibilityTarget=payment, eligibilityAction=APPROVE.
      Prefer eligibility over neo4j_direct for live OPA approver/submitter questions.
      """;

  private final ChatClient chatClient;

  public IntentRouter(ChatClient.Builder chatClientBuilder) {
    this.chatClient = chatClientBuilder.build();
  }

  public RouterDecision route(String question) {
    try {
      RouterDecision decision =
          chatClient
              .prompt()
              .system(ROUTER_SYSTEM)
              .user(question == null ? "" : question)
              .call()
              .entity(RouterDecision.class);
      if (decision == null) {
        throw new IllegalStateException("null RouterDecision from Spring AI");
      }
      log.info(
          "RouterDecision via Spring AI: path={} target={} action={} reasoning={}",
          decision.getPath(),
          decision.getEligibilityTarget(),
          decision.getEligibilityAction(),
          decision.getReasoning());
      return decision;
    } catch (RuntimeException ex) {
      throw ex;
    } catch (Exception ex) {
      throw new IllegalStateException("Spring AI routing failed", ex);
    }
  }
}
