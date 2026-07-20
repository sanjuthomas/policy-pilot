package com.sanjuthomas.policypilot.routing;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.prompts.RouterPrompts;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

@Service
public class IntentRouter {

  private static final Logger log = LoggerFactory.getLogger(IntentRouter.class);

  private final ChatClient chatClient;

  public IntentRouter(ChatClient.Builder chatClientBuilder) {
    this.chatClient = chatClientBuilder.build();
  }

  public RouterDecision route(String question) {
    try {
      RouterDecision decision =
          chatClient
              .prompt()
              .system(RouterPrompts.ROUTER_SYSTEM)
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
