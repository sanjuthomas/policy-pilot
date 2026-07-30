package com.sanjuthomas.policypilot.routing;

import com.sanjuthomas.policypilot.observability.GenAiMetrics;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.prompts.RouterPrompts;
import java.time.LocalDate;
import java.time.ZoneOffset;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

@Service
public class IntentRouter {

  private static final Logger log = LoggerFactory.getLogger(IntentRouter.class);

  private final ChatClient chatClient;
  private final GenAiMetrics genAiMetrics;

  public IntentRouter(ChatClient.Builder chatClientBuilder, GenAiMetrics genAiMetrics) {
    this.chatClient = chatClientBuilder.build();
    this.genAiMetrics = genAiMetrics;
  }

  public RouterDecision route(String question) {
    long startNs = System.nanoTime();
    try {
      String today = LocalDate.now(ZoneOffset.UTC).toString();
      RouterDecision decision =
          chatClient
              .prompt()
              .system(RouterPrompts.ROUTER_SYSTEM + "\nToday's date (UTC): " + today + ".")
              .user(question == null ? "" : question)
              .call()
              .entity(RouterDecision.class);
      if (decision == null) {
        throw new IllegalStateException("null RouterDecision from Spring AI");
      }
      decision = RouteClamps.apply(decision, question);
      genAiMetrics.recordSuccess("chat", (System.nanoTime() - startNs) / 1_000_000.0);
      // Do not log reasoning at INFO — it can restate the user question (PII / secrets).
      log.info(
          "RouterDecision via Spring AI: path={} target={} action={} skill={} graphIntent={}",
          decision.getPath(),
          decision.getEligibilityTarget(),
          decision.getEligibilityAction(),
          decision.getSkill(),
          decision.getGraphIntent());
      if (log.isDebugEnabled()) {
        log.debug("RouterDecision reasoning={}", decision.getReasoning());
      }
      return decision;
    } catch (RuntimeException ex) {
      genAiMetrics.recordError("chat", (System.nanoTime() - startNs) / 1_000_000.0);
      throw ex;
    } catch (Exception ex) {
      genAiMetrics.recordError("chat", (System.nanoTime() - startNs) / 1_000_000.0);
      throw new IllegalStateException("Spring AI routing failed", ex);
    }
  }
}
