package com.policypilot.chatj.service;

import com.policypilot.chatj.api.ApiModels.AnswerRoutingInfo;
import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.eligibility.EligibilityAnswerFormatter;
import com.policypilot.chatj.eligibility.EligibilityClient;
import com.policypilot.chatj.pipeline.RouterDecision;
import com.policypilot.chatj.policydirectory.PolicyDirectoryService;
import com.policypilot.chatj.routing.InstructionIdParser;
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
  private final PolicyDirectoryService policyDirectoryService;

  public ChatService(
      IntentRouter intentRouter,
      EligibilityClient eligibilityClient,
      EligibilityAnswerFormatter eligibilityAnswerFormatter,
      PolicyDirectoryService policyDirectoryService) {
    this.intentRouter = intentRouter;
    this.eligibilityClient = eligibilityClient;
    this.eligibilityAnswerFormatter = eligibilityAnswerFormatter;
    this.policyDirectoryService = policyDirectoryService;
  }

  public ChatResponse ask(ChatRequest request, Subject subject) {
    RouterDecision decision = intentRouter.route(request.message());

    if ("policy_directory".equals(decision.getPath())) {
      return ChatResponse.of(
          policyDirectoryService.answer(request.message(), subject, decision),
          routing("policy_directory", "policy_directory_api"));
    }

    if ("eligibility".equals(decision.getPath())) {
      String target = nullToEmpty(decision.getEligibilityTarget()).toLowerCase();
      String action = nullToEmpty(decision.getEligibilityAction()).toUpperCase();
      if ("payment".equals(target) && "APPROVE".equals(action)) {
        return paymentApprovers(request.message(), subject);
      }
      if ("payment".equals(target) && "SUBMIT".equals(action)) {
        return paymentSubmitters(request.message(), subject);
      }
      if ("instruction".equals(target)
          && (action.isEmpty() || "APPROVE".equals(action))) {
        return instructionApprovers(request.message(), subject);
      }
    }

    return ChatResponse.of(
        "ssi-chat-j answers payment/instruction eligibility and policy-directory questions "
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
        eligibilityAnswerFormatter.formatEligiblePaymentApproversAnswer(data),
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
        eligibilityAnswerFormatter.formatEligiblePaymentSubmittersAnswer(data),
        routing("eligibility", "eligibility_api"));
  }

  private ChatResponse instructionApprovers(String message, Subject subject) {
    Optional<String> instructionId = InstructionIdParser.extract(message);
    if (instructionId.isEmpty()) {
      return ChatResponse.of(
          "Please include an instruction id, for example: "
              + "Who can approve instruction 20260720-FICC-I-1?",
          routing("eligibility", "eligibility_api"));
    }
    Map<String, Object> data =
        eligibilityClient.eligibleApproversForInstruction(
            instructionId.get(), subject.bearerToken(), subject.sessionId());
    return ChatResponse.of(
        eligibilityAnswerFormatter.formatEligibleInstructionApproversAnswer(data),
        routing("eligibility", "eligibility_api"));
  }

  private static AnswerRoutingInfo routing(String path, String synthesis) {
    String label =
        switch (path) {
          case "eligibility" -> "Eligibility API (OPA)";
          case "policy_directory" -> "Policy directory API";
          default -> "ssi-chat-j (" + path + ")";
        };
    String retrievalStrategy =
        switch (path) {
          case "eligibility" -> "eligibility";
          case "policy_directory" -> "policy_directory";
          default -> null;
        };
    return new AnswerRoutingInfo(
        path, "none", synthesis, label, null, retrievalStrategy, null);
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
