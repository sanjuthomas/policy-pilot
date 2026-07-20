package com.policypilot.chatj.service;

import com.policypilot.chatj.api.ApiModels.AnswerRoutingInfo;
import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.eligibility.EligibilityAnswerFormatter;
import com.policypilot.chatj.eligibility.EligibilityClient;
import com.policypilot.chatj.pipeline.RouterDecision;
import com.policypilot.chatj.routing.IntentRouter;
import com.policypilot.chatj.routing.PaymentIdParser;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;

@Service
public class ChatService {

  private final IntentRouter intentRouter;
  private final EligibilityClient eligibilityClient;
  private final EligibilityAnswerFormatter eligibilityAnswerFormatter;

  public ChatService(
      IntentRouter intentRouter,
      EligibilityClient eligibilityClient,
      EligibilityAnswerFormatter eligibilityAnswerFormatter) {
    this.intentRouter = intentRouter;
    this.eligibilityClient = eligibilityClient;
    this.eligibilityAnswerFormatter = eligibilityAnswerFormatter;
  }

  public ChatResponse ask(ChatRequest request, Subject subject) {
    RouterDecision decision = intentRouter.route(request.message());

    if ("eligibility".equals(decision.getPath())
        && "payment".equalsIgnoreCase(nullToEmpty(decision.getEligibilityTarget()))) {
      String action = nullToEmpty(decision.getEligibilityAction()).toUpperCase();
      if ("APPROVE".equals(action)) {
        return paymentApprovers(request.message(), subject);
      }
      if ("SUBMIT".equals(action)) {
        return paymentSubmitters(request.message(), subject);
      }
    }

    return ChatResponse.of(
        "ssi-chat-j answers payment eligibility (APPROVE / SUBMIT) questions "
            + "(e.g. Who can approve payment 20260720-FICC-P-8?). "
            + "Routed as path="
            + decision.getPath()
            + ".",
        routing(decision.getPath(), "stub"));
  }

  private ChatResponse paymentApprovers(String message, Subject subject) {
    Optional<String> paymentId = PaymentIdParser.extract(message);
    if (paymentId.isEmpty()) {
      return ChatResponse.of(
          "Please include a payment id, for example: "
              + "Who can approve payment 20260720-FICC-P-8?",
          routing("eligibility", "eligibility_api"));
    }
    Map<String, Object> data =
        eligibilityClient.eligibleApproversForPayment(
            paymentId.get(), subject.bearerToken(), subject.sessionId());
    return ChatResponse.of(
        eligibilityAnswerFormatter.formatEligibleApproversAnswer(data),
        routing("eligibility", "eligibility_api"));
  }

  private ChatResponse paymentSubmitters(String message, Subject subject) {
    Optional<String> paymentId = PaymentIdParser.extract(message);
    if (paymentId.isEmpty()) {
      return ChatResponse.of(
          "Please include a payment id, for example: "
              + "Who can submit payment 20260720-FICC-P-8 for approval?",
          routing("eligibility", "eligibility_api"));
    }
    Map<String, Object> data =
        eligibilityClient.eligibleSubmittersForPayment(
            paymentId.get(), subject.bearerToken(), subject.sessionId());
    return ChatResponse.of(
        eligibilityAnswerFormatter.formatEligibleSubmittersAnswer(data),
        routing("eligibility", "eligibility_api"));
  }

  private static AnswerRoutingInfo routing(String path, String synthesis) {
    String label =
        "eligibility".equals(path)
            ? "Eligibility API (OPA)"
            : "ssi-chat-j M1 (" + path + ")";
    String retrievalStrategy = "eligibility".equals(path) ? "eligibility" : null;
    return new AnswerRoutingInfo(
        path, "none", synthesis, label, null, retrievalStrategy, null);
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
