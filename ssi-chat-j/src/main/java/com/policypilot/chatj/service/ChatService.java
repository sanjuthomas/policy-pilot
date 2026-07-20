package com.policypilot.chatj.service;

import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.eligibility.EligibilityAnswerFormatter;
import com.policypilot.chatj.eligibility.EligibilityClient;
import com.policypilot.chatj.observability.ChatAnswerFinalizer;
import com.policypilot.chatj.pipeline.RouterDecision;
import com.policypilot.chatj.policydirectory.PolicyDirectoryService;
import com.policypilot.chatj.policysummary.PolicySummaryAnswerFormatter;
import com.policypilot.chatj.routing.InstructionIdParser;
import com.policypilot.chatj.routing.IntentRouter;
import com.policypilot.chatj.routing.PaymentIdParser;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class ChatService {

  private final IntentRouter intentRouter;
  private final EligibilityClient eligibilityClient;
  private final EligibilityAnswerFormatter eligibilityAnswerFormatter;
  private final PolicyDirectoryService policyDirectoryService;
  private final PolicySummaryAnswerFormatter policySummaryAnswerFormatter;
  private final ChatAnswerFinalizer answerFinalizer;

  public ChatService(
      IntentRouter intentRouter,
      EligibilityClient eligibilityClient,
      EligibilityAnswerFormatter eligibilityAnswerFormatter,
      PolicyDirectoryService policyDirectoryService,
      PolicySummaryAnswerFormatter policySummaryAnswerFormatter,
      ChatAnswerFinalizer answerFinalizer) {
    this.intentRouter = intentRouter;
    this.eligibilityClient = eligibilityClient;
    this.eligibilityAnswerFormatter = eligibilityAnswerFormatter;
    this.policyDirectoryService = policyDirectoryService;
    this.policySummaryAnswerFormatter = policySummaryAnswerFormatter;
    this.answerFinalizer = answerFinalizer;
  }

  public ChatResponse ask(ChatRequest request, Subject subject) {
    long routeStartNs = System.nanoTime();
    RouterDecision decision = intentRouter.route(request.message());
    double generationMs = (System.nanoTime() - routeStartNs) / 1_000_000.0;
    String requestedPath = decision.getPath();

    if ("policy_summary".equals(decision.getPath())) {
      return policySummary(request, subject, decision, requestedPath, generationMs);
    }

    if ("policy_directory".equals(decision.getPath())) {
      long retrievalStartNs = System.nanoTime();
      String answer = policyDirectoryService.answer(request.message(), subject, decision);
      double retrievalMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;
      return answer(
          request,
          answer,
          "policy_directory",
          "policy_directory_api",
          requestedPath,
          retrievalMs,
          generationMs);
    }

    if ("eligibility".equals(decision.getPath())) {
      String target = nullToEmpty(decision.getEligibilityTarget()).toLowerCase();
      String action = nullToEmpty(decision.getEligibilityAction()).toUpperCase();
      if ("payment".equals(target) && "APPROVE".equals(action)) {
        return paymentApprovers(request, subject, requestedPath, generationMs);
      }
      if ("payment".equals(target) && "SUBMIT".equals(action)) {
        return paymentSubmitters(request, subject, requestedPath, generationMs);
      }
      if ("instruction".equals(target)
          && (action.isEmpty() || "APPROVE".equals(action))) {
        return instructionApprovers(request, subject, requestedPath, generationMs);
      }
    }

    return answer(
        request,
        "ssi-chat-j answers payment/instruction eligibility, policy-directory, and "
            + "policy-summary questions "
            + "(e.g. Who can approve payment 20260720-FICC-P-8?). "
            + "Routed as path="
            + decision.getPath()
            + ".",
        decision.getPath(),
        "stub",
        requestedPath,
        0.0,
        generationMs);
  }

  private ChatResponse policySummary(
      ChatRequest request,
      Subject subject,
      RouterDecision decision,
      String requestedPath,
      double generationMs) {
    String domain =
        StringUtils.hasText(decision.getPolicyDomain())
            ? decision.getPolicyDomain().strip().toLowerCase()
            : "payment";
    String action =
        StringUtils.hasText(decision.getPolicyAction())
            ? decision.getPolicyAction().strip().toUpperCase()
            : "APPROVE";
    long retrievalStartNs = System.nanoTime();
    Map<String, Object> data =
        eligibilityClient.policySummary(
            domain, action, subject.bearerToken(), subject.sessionId());
    String answerText = policySummaryAnswerFormatter.format(data);
    double retrievalMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;
    return answer(
        request,
        answerText,
        "policy_summary",
        "eligibility_api",
        requestedPath,
        retrievalMs,
        generationMs);
  }

  private ChatResponse paymentApprovers(
      ChatRequest request, Subject subject, String requestedPath, double generationMs) {
    Optional<String> paymentId = PaymentIdParser.extract(request.message());
    if (paymentId.isEmpty()) {
      return answer(
          request,
          "Please include a payment id, for example: "
              + "Who can approve payment 20260720-FICC-P-8?",
          "eligibility",
          "eligibility_api",
          requestedPath,
          0.0,
          generationMs);
    }
    long retrievalStartNs = System.nanoTime();
    Map<String, Object> data =
        eligibilityClient.eligibleApproversForPayment(
            paymentId.get(), subject.bearerToken(), subject.sessionId());
    String answerText = eligibilityAnswerFormatter.formatEligiblePaymentApproversAnswer(data);
    double retrievalMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;
    return answer(
        request,
        answerText,
        "eligibility",
        "eligibility_api",
        requestedPath,
        retrievalMs,
        generationMs);
  }

  private ChatResponse paymentSubmitters(
      ChatRequest request, Subject subject, String requestedPath, double generationMs) {
    Optional<String> paymentId = PaymentIdParser.extract(request.message());
    if (paymentId.isEmpty()) {
      return answer(
          request,
          "Please include a payment id, for example: "
              + "Who can submit payment 20260720-FICC-P-8 for approval?",
          "eligibility",
          "eligibility_api",
          requestedPath,
          0.0,
          generationMs);
    }
    long retrievalStartNs = System.nanoTime();
    Map<String, Object> data =
        eligibilityClient.eligibleSubmittersForPayment(
            paymentId.get(), subject.bearerToken(), subject.sessionId());
    String answerText = eligibilityAnswerFormatter.formatEligiblePaymentSubmittersAnswer(data);
    double retrievalMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;
    return answer(
        request,
        answerText,
        "eligibility",
        "eligibility_api",
        requestedPath,
        retrievalMs,
        generationMs);
  }

  private ChatResponse instructionApprovers(
      ChatRequest request, Subject subject, String requestedPath, double generationMs) {
    Optional<String> instructionId = InstructionIdParser.extract(request.message());
    if (instructionId.isEmpty()) {
      return answer(
          request,
          "Please include an instruction id, for example: "
              + "Who can approve instruction 20260720-FICC-I-1?",
          "eligibility",
          "eligibility_api",
          requestedPath,
          0.0,
          generationMs);
    }
    long retrievalStartNs = System.nanoTime();
    Map<String, Object> data =
        eligibilityClient.eligibleApproversForInstruction(
            instructionId.get(), subject.bearerToken(), subject.sessionId());
    String answerText = eligibilityAnswerFormatter.formatEligibleInstructionApproversAnswer(data);
    double retrievalMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;
    return answer(
        request,
        answerText,
        "eligibility",
        "eligibility_api",
        requestedPath,
        retrievalMs,
        generationMs);
  }

  private ChatResponse answer(
      ChatRequest request,
      String answerText,
      String path,
      String synthesis,
      String requestedPath,
      double retrievalMs,
      double generationMs) {
    if (answerFinalizer == null) {
      return ChatResponse.of(answerText, null);
    }
    return answerFinalizer.of(
        request.message(),
        request.mode(),
        answerText,
        path,
        synthesis,
        requestedPath,
        retrievalMs,
        generationMs);
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
