package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityClient;
import com.sanjuthomas.policypilot.extraction.EntityApiQuestion.Facet;
import com.sanjuthomas.policypilot.instruction.InstructionDetailAnswerFormatter;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

/**
 * Document extraction lane: payment / instruction GET, list, and versions via domain APIs (OBO),
 * not Neo4j. Open-vocabulary status/type come from {@link RouterDecision} LLM slots.
 */
@Service
public class DocumentExtractionService {

  private final EligibilityClient eligibilityClient;
  private final InstructionDetailAnswerFormatter instructionDetailAnswerFormatter;
  private final PaymentDetailAnswerFormatter paymentDetailAnswerFormatter;
  private final EntityApiAnswerFormatter entityApiAnswerFormatter;

  public DocumentExtractionService(
      EligibilityClient eligibilityClient,
      InstructionDetailAnswerFormatter instructionDetailAnswerFormatter,
      PaymentDetailAnswerFormatter paymentDetailAnswerFormatter,
      EntityApiAnswerFormatter entityApiAnswerFormatter) {
    this.eligibilityClient = eligibilityClient;
    this.instructionDetailAnswerFormatter = instructionDetailAnswerFormatter;
    this.paymentDetailAnswerFormatter = paymentDetailAnswerFormatter;
    this.entityApiAnswerFormatter = entityApiAnswerFormatter;
  }

  public DocumentExtractionResult answer(String question, Subject subject, RouterDecision decision) {
    Facet facet = EntityApiQuestion.resolveFacet(question, decision);
    if (EntityApiQuestion.isInventoryFacet(facet)) {
      return listInstructions(question, subject, decision, facet);
    }

    String target = resolveTarget(question, decision);
    if ("payment".equals(target)) {
      return answerPayment(question, subject, facet);
    }
    if ("instruction".equals(target)) {
      return answerInstruction(question, subject, facet);
    }
    return new DocumentExtractionResult(
        "Please include a payment or instruction id, for example: "
            + "Show me instruction 20260720-FICC-I-1 or Show me payment 20260720-FICC-P-8",
        "document.show_by_id");
  }

  private DocumentExtractionResult listInstructions(
      String question, Subject subject, RouterDecision decision, Facet facet) {
    Facet resolved = facet;
    String status = EntityApiQuestion.resolveEntityStatus(question, decision);
    String type = EntityApiQuestion.resolveInstructionType(question, decision);
    String createdBy = null;
    String intentId =
        switch (resolved) {
          case LIST_STANDING -> {
            if (!StringUtils.hasText(type)) {
              type = "STANDING";
            }
            yield "instruction.list_standing";
          }
          case LIST_SINGLE_USE -> {
            if (!StringUtils.hasText(type)) {
              type = "SINGLE_USE";
            }
            yield "instruction.list_single_use";
          }
          case CREATED_BY_USER -> {
            createdBy = EntityApiQuestion.extractUserId(question).orElse(null);
            yield "instruction.created_by_user";
          }
          default -> "instruction.list_by_status";
        };
    if (resolved == Facet.CREATED_BY_USER && createdBy == null) {
      return new DocumentExtractionResult(
          "Please include a user id (for example mo-050) when asking which instructions a user created.",
          intentId);
    }
    if (resolved == Facet.LIST_BY_STATUS && !StringUtils.hasText(status) && !StringUtils.hasText(type)) {
      return new DocumentExtractionResult(
          "Please name a status or type when listing instructions "
              + "(or ask again so status can be resolved).",
          intentId);
    }
    try {
      List<Map<String, Object>> rows =
          eligibilityClient.listInstructions(
              status,
              type,
              createdBy,
              EntityApiQuestion.lobFilter(question),
              200,
              subject.bearerToken(),
              subject.sessionId());
      return new DocumentExtractionResult(
          entityApiAnswerFormatter.formatInstructionInventory(rows), intentId);
    } catch (ResponseStatusException ex) {
      return mapHttpError(
          ex,
          "No matching instructions were found.",
          "You are not authorized to list these instructions.",
          intentId);
    }
  }

  private DocumentExtractionResult answerInstruction(
      String question, Subject subject, Facet facet) {
    Optional<String> instructionId = InstructionIdParser.extract(question);
    if (instructionId.isEmpty()) {
      return new DocumentExtractionResult(
          "Please include an instruction id, for example: "
              + "Show me instruction 20260720-FICC-I-1",
          "instruction.show_by_id");
    }
    if (facet == Facet.VERSIONS) {
      return instructionVersions(instructionId.get(), subject);
    }
    try {
      Map<String, Object> data =
          eligibilityClient.getInstruction(
              instructionId.get(), subject.bearerToken(), subject.sessionId());
      return switch (facet) {
        case STATUS ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatInstructionStatus(data),
                "instruction.status_by_id");
        case CREATOR ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatInstructionCreator(data),
                "instruction.creator_by_id");
        case CREATOR_AND_APPROVER ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatInstructionCreatorAndApprover(data),
                "instruction.creator_and_approver_by_id");
        case APPROVER ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatInstructionApprover(data),
                "instruction.approver_by_id");
        default ->
            new DocumentExtractionResult(
                instructionDetailAnswerFormatter.format(data), "instruction.show_by_id");
      };
    } catch (ResponseStatusException ex) {
      String intent =
          switch (facet) {
            case STATUS -> "instruction.status_by_id";
            case CREATOR -> "instruction.creator_by_id";
            case CREATOR_AND_APPROVER -> "instruction.creator_and_approver_by_id";
            case APPROVER -> "instruction.approver_by_id";
            default -> "instruction.show_by_id";
          };
      return mapHttpError(
          ex,
          "No instruction with that ID was found.",
          "You are not authorized to view this instruction.",
          intent);
    }
  }

  private DocumentExtractionResult answerPayment(String question, Subject subject, Facet facet) {
    Optional<String> paymentId = PaymentIdParser.extract(question);
    if (paymentId.isEmpty()) {
      return new DocumentExtractionResult(
          "Please include a payment id, for example: Show me payment 20260720-FICC-P-8",
          "payment.show_by_id");
    }
    if (facet == Facet.VERSIONS) {
      return paymentVersions(paymentId.get(), subject);
    }
    try {
      Map<String, Object> data =
          eligibilityClient.getPayment(
              paymentId.get(), subject.bearerToken(), subject.sessionId());
      return switch (facet) {
        case STATUS ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatPaymentStatus(data), "payment.status_by_id");
        case CREATOR ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatPaymentCreator(data), "payment.creator_by_id");
        case CREATOR_AND_APPROVER ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatPaymentCreatorAndApprover(data),
                "payment.creator_and_approver_by_id");
        case APPROVER ->
            new DocumentExtractionResult(
                entityApiAnswerFormatter.formatPaymentApprover(data), "payment.approver_by_id");
        default ->
            new DocumentExtractionResult(
                paymentDetailAnswerFormatter.format(data), "payment.show_by_id");
      };
    } catch (ResponseStatusException ex) {
      String intent =
          switch (facet) {
            case STATUS -> "payment.status_by_id";
            case CREATOR -> "payment.creator_by_id";
            case CREATOR_AND_APPROVER -> "payment.creator_and_approver_by_id";
            case APPROVER -> "payment.approver_by_id";
            default -> "payment.show_by_id";
          };
      return mapHttpError(
          ex,
          "No payment with that ID was found.",
          "You are not authorized to view this payment.",
          intent);
    }
  }

  private DocumentExtractionResult instructionVersions(String instructionId, Subject subject) {
    try {
      List<Map<String, Object>> rows =
          eligibilityClient.listInstructionVersions(
              instructionId, subject.bearerToken(), subject.sessionId());
      return new DocumentExtractionResult(
          entityApiAnswerFormatter.formatInstructionVersions(instructionId, rows),
          "instruction.versions_by_id");
    } catch (ResponseStatusException ex) {
      return mapHttpError(
          ex,
          "No instruction with that ID was found.",
          "You are not authorized to view this instruction.",
          "instruction.versions_by_id");
    }
  }

  private DocumentExtractionResult paymentVersions(String paymentId, Subject subject) {
    try {
      List<Map<String, Object>> rows =
          eligibilityClient.listPaymentVersions(
              paymentId, subject.bearerToken(), subject.sessionId());
      return new DocumentExtractionResult(
          entityApiAnswerFormatter.formatPaymentVersions(paymentId, rows),
          "payment.versions_by_id");
    } catch (ResponseStatusException ex) {
      return mapHttpError(
          ex,
          "No payment with that ID was found.",
          "You are not authorized to view this payment.",
          "payment.versions_by_id");
    }
  }

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
