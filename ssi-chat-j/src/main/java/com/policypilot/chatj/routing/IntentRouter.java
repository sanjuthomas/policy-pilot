package com.policypilot.chatj.routing;

import com.policypilot.chatj.pipeline.RouterDecision;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

@Service
public class IntentRouter {

  private static final Logger log = LoggerFactory.getLogger(IntentRouter.class);

  private static final Pattern PAYMENT_APPROVE =
      Pattern.compile(
          "(?i)\\bwho\\s+can\\s+approve\\s+(?:this\\s+)?payment\\s+([A-Za-z0-9._:-]+)\\b");

  private static final String ROUTER_SYSTEM =
      """
      You are the Policy Pilot chat intent router.
      Return ONLY a RouterDecision JSON object.
      For questions like "Who can approve payment PAY-...?" set:
        path=eligibility, strategy=eligibility, eligibilityTarget=payment, eligibilityAction=APPROVE.
      Prefer eligibility over neo4j_direct for live OPA approver/submitter questions.
      """;

  private final ObjectProvider<ChatClient.Builder> chatClientBuilder;

  public IntentRouter(ObjectProvider<ChatClient.Builder> chatClientBuilder) {
    this.chatClientBuilder = chatClientBuilder;
  }

  public RouterDecision route(String question) {
    RouterDecision heuristic = heuristicEligibility(question).orElse(null);
    ChatClient.Builder builder = chatClientBuilder.getIfAvailable();
    if (builder == null) {
      if (heuristic != null) {
        log.info("RouterDecision via heuristic (no ChatClient): path={}", heuristic.getPath());
        return heuristic;
      }
      return unsupported(question);
    }
    try {
      RouterDecision decision =
          builder
              .build()
              .prompt()
              .system(ROUTER_SYSTEM)
              .user(question)
              .call()
              .entity(RouterDecision.class);
      if (decision == null) {
        throw new IllegalStateException("null RouterDecision from Spring AI");
      }
      decision.normalize();
      // Slot fill: LLM may omit payment id; keep target/action from model/heuristic.
      if ("eligibility".equals(decision.getPath())
          && "payment".equalsIgnoreCase(decision.getEligibilityTarget())
          && heuristic != null
          && "APPROVE".equalsIgnoreCase(decision.getEligibilityAction())) {
        // heuristic already matched approve-payment shape
      }
      log.info(
          "RouterDecision via Spring AI: path={} target={} action={} reasoning={}",
          decision.getPath(),
          decision.getEligibilityTarget(),
          decision.getEligibilityAction(),
          decision.getReasoning());
      return decision;
    } catch (Exception ex) {
      log.warn("Spring AI routing failed, falling back: {}", ex.toString());
      if (heuristic != null) {
        return heuristic;
      }
      return unsupported(question);
    }
  }

  public Optional<String> extractPaymentId(String question) {
    Matcher matcher = PAYMENT_APPROVE.matcher(question == null ? "" : question);
    if (matcher.find()) {
      return Optional.of(matcher.group(1).replaceAll("[?.!,;:]+$", ""));
    }
    // Broader: payment ID token after "payment"
    Matcher loose =
        Pattern.compile("(?i)\\bpayment\\s+([A-Za-z0-9._:-]+)").matcher(question == null ? "" : question);
    if (loose.find()) {
      return Optional.of(loose.group(1).replaceAll("[?.!,;:]+$", ""));
    }
    return Optional.empty();
  }

  Optional<RouterDecision> heuristicEligibility(String question) {
    String q = question == null ? "" : question.toLowerCase(Locale.ROOT);
    if (PAYMENT_APPROVE.matcher(question == null ? "" : question).find()
        || (q.contains("who can approve") && q.contains("payment"))) {
      RouterDecision decision = new RouterDecision();
      decision.setPath("eligibility");
      decision.setStrategy("eligibility");
      decision.setEligibilityTarget("payment");
      decision.setEligibilityAction("APPROVE");
      decision.setReasoning("heuristic: who-can-approve payment");
      decision.normalize();
      return Optional.of(decision);
    }
    return Optional.empty();
  }

  private static RouterDecision unsupported(String question) {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    decision.setReasoning("M1 stub: only payment eligibility is implemented");
    decision.normalize();
    return decision;
  }
}
