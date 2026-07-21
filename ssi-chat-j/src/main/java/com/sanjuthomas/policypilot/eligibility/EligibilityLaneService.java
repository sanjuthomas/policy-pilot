package com.sanjuthomas.policypilot.eligibility;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.util.Map;
import java.util.Optional;
import org.springframework.stereotype.Service;

/**
 * Eligibility path lane: payment APPROVE / SUBMIT and instruction APPROVE via OBO APIs.
 */
@Service
public class EligibilityLaneService {

  private final EligibilityClient eligibilityClient;
  private final EligibilityAnswerFormatter eligibilityAnswerFormatter;

  public EligibilityLaneService(
      EligibilityClient eligibilityClient, EligibilityAnswerFormatter eligibilityAnswerFormatter) {
    this.eligibilityClient = eligibilityClient;
    this.eligibilityAnswerFormatter = eligibilityAnswerFormatter;
  }

  /**
   * @return lane answer, or {@code null} when target/action is not handled (ChatService stub).
   */
  public LaneAnswer answer(String message, Subject subject, RouterDecision decision) {
    String target = nullToEmpty(decision.getEligibilityTarget()).toLowerCase();
    String action = nullToEmpty(decision.getEligibilityAction()).toUpperCase();
    if ("payment".equals(target) && "APPROVE".equals(action)) {
      return paymentApprovers(message, subject);
    }
    if ("payment".equals(target) && "SUBMIT".equals(action)) {
      return paymentSubmitters(message, subject);
    }
    if ("instruction".equals(target) && (action.isEmpty() || "APPROVE".equals(action))) {
      return instructionApprovers(message, subject);
    }
    return null;
  }

  private LaneAnswer paymentApprovers(String message, Subject subject) {
    Optional<String> paymentId = PaymentIdParser.extract(message);
    if (paymentId.isEmpty()) {
      return eligibility(
          "Please include a payment id, for example: "
              + "Who can approve payment 20260720-FICC-P-8?");
    }
    Map<String, Object> data =
        eligibilityClient.eligibleApproversForPayment(
            paymentId.get(), subject.bearerToken(), subject.sessionId());
    return eligibility(eligibilityAnswerFormatter.formatEligiblePaymentApproversAnswer(data));
  }

  private LaneAnswer paymentSubmitters(String message, Subject subject) {
    Optional<String> paymentId = PaymentIdParser.extract(message);
    if (paymentId.isEmpty()) {
      return eligibility(
          "Please include a payment id, for example: "
              + "Who can submit payment 20260720-FICC-P-8 for approval?");
    }
    Map<String, Object> data =
        eligibilityClient.eligibleSubmittersForPayment(
            paymentId.get(), subject.bearerToken(), subject.sessionId());
    return eligibility(eligibilityAnswerFormatter.formatEligiblePaymentSubmittersAnswer(data));
  }

  private LaneAnswer instructionApprovers(String message, Subject subject) {
    Optional<String> instructionId = InstructionIdParser.extract(message);
    if (instructionId.isEmpty()) {
      return eligibility(
          "Please include an instruction id, for example: "
              + "Who can approve instruction 20260720-FICC-I-1?");
    }
    Map<String, Object> data =
        eligibilityClient.eligibleApproversForInstruction(
            instructionId.get(), subject.bearerToken(), subject.sessionId());
    return eligibility(eligibilityAnswerFormatter.formatEligibleInstructionApproversAnswer(data));
  }

  private static LaneAnswer eligibility(String answer) {
    return LaneAnswer.of(answer, "eligibility", "eligibility_api");
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
