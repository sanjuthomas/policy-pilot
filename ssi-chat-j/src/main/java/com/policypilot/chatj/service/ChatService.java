package com.policypilot.chatj.service;

import com.policypilot.chatj.api.ApiModels.AnswerRoutingInfo;
import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.eligibility.EligibilityClient;
import com.policypilot.chatj.eligibility.EligibilityFormatter;
import com.policypilot.chatj.pipeline.RouterDecision;
import com.policypilot.chatj.routing.IntentRouter;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;

@Service
public class ChatService {

  private final IntentRouter intentRouter;
  private final EligibilityClient eligibilityClient;

  public ChatService(IntentRouter intentRouter, EligibilityClient eligibilityClient) {
    this.intentRouter = intentRouter;
    this.eligibilityClient = eligibilityClient;
  }

  public ChatResponse ask(ChatRequest request, Subject subject) {
    RouterDecision decision = intentRouter.route(request.message());
    decision.normalize();

    if ("eligibility".equals(decision.getPath())
        && "payment".equalsIgnoreCase(nullToEmpty(decision.getEligibilityTarget()))
        && "APPROVE".equalsIgnoreCase(nullToEmpty(decision.getEligibilityAction()))) {
      Optional<String> paymentId = intentRouter.extractPaymentId(request.message());
      if (paymentId.isEmpty()) {
        return ChatResponse.of(
            "Please include a payment id, for example: Who can approve payment PAY-…?",
            routing("eligibility", "eligibility_api", decision));
      }
      Map<String, Object> data =
          eligibilityClient.eligibleApproversForPayment(
              paymentId.get(), subject.bearerToken(), subject.sessionId());
      String answer = EligibilityFormatter.formatEligibleApproversAnswer(data);
      return ChatResponse.of(answer, routing("eligibility", "eligibility_api", decision));
    }

    return ChatResponse.of(
        "ssi-chat-j M1 only answers payment eligibility questions "
            + "(e.g. Who can approve payment PAY-…). "
            + "Routed as path="
            + decision.getPath()
            + ".",
        routing(decision.getPath(), "stub", decision));
  }

  private static AnswerRoutingInfo routing(
      String path, String synthesis, RouterDecision decision) {
    String label =
        "eligibility".equals(path)
            ? "Eligibility API (OPA)"
            : "ssi-chat-j M1 (" + path + ")";
    return new AnswerRoutingInfo(
        path,
        "none",
        synthesis,
        label,
        null,
        "eligibility".equals(path) ? "eligibility" : decision.getStrategy(),
        null);
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
