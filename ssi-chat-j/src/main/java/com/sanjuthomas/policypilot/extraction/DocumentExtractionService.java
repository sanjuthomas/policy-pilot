package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.instruction.InstructionDetailAnswerFormatter;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.util.Map;
import java.util.Optional;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/**
 * Document extraction lane: show payment / instruction by id via domain APIs (OBO), not Neo4j.
 * LOB / authz are enforced by payment-service and instruction-service.
 */
@Service
public class DocumentExtractionService {

  private final EligibilityClient eligibilityClient;
  private final InstructionDetailAnswerFormatter instructionDetailAnswerFormatter;
  private final PaymentDetailAnswerFormatter paymentDetailAnswerFormatter;

  public DocumentExtractionService(
      EligibilityClient eligibilityClient,
      InstructionDetailAnswerFormatter instructionDetailAnswerFormatter,
      PaymentDetailAnswerFormatter paymentDetailAnswerFormatter) {
    this.eligibilityClient = eligibilityClient;
    this.instructionDetailAnswerFormatter = instructionDetailAnswerFormatter;
    this.paymentDetailAnswerFormatter = paymentDetailAnswerFormatter;
  }

  public DocumentExtractionResult answer(String question, Subject subject, RouterDecision decision) {
    String target = resolveTarget(question, decision);
    if ("payment".equals(target)) {
      return showPayment(question, subject);
    }
    if ("instruction".equals(target)) {
      return showInstruction(question, subject);
    }
    return new DocumentExtractionResult(
        "Please include a payment or instruction id, for example: "
            + "Show me instruction 20260720-FICC-I-1 or Show me payment 20260720-FICC-P-8",
        "document.show_by_id");
  }

  private DocumentExtractionResult showInstruction(String question, Subject subject) {
    Optional<String> instructionId = InstructionIdParser.extract(question);
    if (instructionId.isEmpty()) {
      return new DocumentExtractionResult(
          "Please include an instruction id, for example: "
              + "Show me instruction 20260720-FICC-I-1",
          "instruction.show_by_id");
    }
    try {
      Map<String, Object> data =
          eligibilityClient.getInstruction(
              instructionId.get(), subject.bearerToken(), subject.sessionId());
      return new DocumentExtractionResult(
          instructionDetailAnswerFormatter.format(data), "instruction.show_by_id");
    } catch (ResponseStatusException ex) {
      return mapHttpError(
          ex,
          "No instruction with that ID was found.",
          "You are not authorized to view this instruction.",
          "instruction.show_by_id");
    }
  }

  private DocumentExtractionResult showPayment(String question, Subject subject) {
    Optional<String> paymentId = PaymentIdParser.extract(question);
    if (paymentId.isEmpty()) {
      return new DocumentExtractionResult(
          "Please include a payment id, for example: Show me payment 20260720-FICC-P-8",
          "payment.show_by_id");
    }
    try {
      Map<String, Object> data =
          eligibilityClient.getPayment(
              paymentId.get(), subject.bearerToken(), subject.sessionId());
      return new DocumentExtractionResult(
          paymentDetailAnswerFormatter.format(data), "payment.show_by_id");
    } catch (ResponseStatusException ex) {
      return mapHttpError(
          ex,
          "No payment with that ID was found.",
          "You are not authorized to view this payment.",
          "payment.show_by_id");
    }
  }

  /**
   * Prefer router {@code extractionTarget}; otherwise infer from sequence id shape (-P- vs -I-).
   */
  static String resolveTarget(String question, RouterDecision decision) {
    String fromRouter =
        decision == null ? "" : nullToEmpty(decision.getExtractionTarget()).toLowerCase().strip();
    if ("payment".equals(fromRouter) || "instruction".equals(fromRouter)) {
      return fromRouter;
    }
    if (PaymentIdParser.extract(question).isPresent()) {
      return "payment";
    }
    if (InstructionIdParser.extract(question).isPresent()) {
      return "instruction";
    }
    return "";
  }

  private static DocumentExtractionResult mapHttpError(
      ResponseStatusException ex,
      String notFoundMessage,
      String forbiddenMessage,
      String intentId) {
    if (ex.getStatusCode() == HttpStatus.NOT_FOUND) {
      return new DocumentExtractionResult(notFoundMessage, intentId);
    }
    if (ex.getStatusCode() == HttpStatus.FORBIDDEN) {
      return new DocumentExtractionResult(forbiddenMessage, intentId);
    }
    throw ex;
  }

  private static String nullToEmpty(String value) {
    return value == null ? "" : value;
  }
}
