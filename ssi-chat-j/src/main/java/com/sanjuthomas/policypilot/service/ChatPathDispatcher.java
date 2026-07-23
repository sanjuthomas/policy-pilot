package com.sanjuthomas.policypilot.service;

import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.EligibilityLaneService;
import com.sanjuthomas.policypilot.extraction.DocumentExtractionResult;
import com.sanjuthomas.policypilot.extraction.DocumentExtractionService;
import com.sanjuthomas.policypilot.me.MeIntentResult;
import com.sanjuthomas.policypilot.me.MeIntentService;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectService;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectService.Neo4jDirectResult;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.person.PersonPermissionSummaryService;
import com.sanjuthomas.policypilot.policydirectory.PolicyDirectoryService;
import com.sanjuthomas.policypilot.policysummary.PolicySummaryService;
import com.sanjuthomas.policypilot.vector.FullRagLaneService;
import org.springframework.stereotype.Component;

/**
 * Maps {@link RouterDecision#getPath()} to lane services. Returns {@code null} for unknown /
 * unhandled paths so {@link ChatService} can emit the capability stub.
 */
@Component
public class ChatPathDispatcher {

  private final MeIntentService meIntentService;
  private final EligibilityLaneService eligibilityLaneService;
  private final PolicySummaryService policySummaryService;
  private final PersonPermissionSummaryService personPermissionSummaryService;
  private final PolicyDirectoryService policyDirectoryService;
  private final DocumentExtractionService documentExtractionService;
  private final Neo4jDirectService neo4jDirectService;
  private final FullRagLaneService fullRagLaneService;

  public ChatPathDispatcher(
      MeIntentService meIntentService,
      EligibilityLaneService eligibilityLaneService,
      PolicySummaryService policySummaryService,
      PersonPermissionSummaryService personPermissionSummaryService,
      PolicyDirectoryService policyDirectoryService,
      DocumentExtractionService documentExtractionService,
      Neo4jDirectService neo4jDirectService,
      FullRagLaneService fullRagLaneService) {
    this.meIntentService = meIntentService;
    this.eligibilityLaneService = eligibilityLaneService;
    this.policySummaryService = policySummaryService;
    this.personPermissionSummaryService = personPermissionSummaryService;
    this.policyDirectoryService = policyDirectoryService;
    this.documentExtractionService = documentExtractionService;
    this.neo4jDirectService = neo4jDirectService;
    this.fullRagLaneService = fullRagLaneService;
  }

  public LaneAnswer dispatch(RouterDecision decision, ChatRequest request, Subject subject) {
    if (decision == null || decision.getPath() == null) {
      return null;
    }
    return switch (decision.getPath()) {
      case "me" -> me(request, subject, decision);
      case "policy_summary" -> policySummaryService.answer(subject, decision);
      case "person_permissions" ->
          personPermissionSummaryService.answer(request.message(), subject, decision);
      case "policy_directory" ->
          LaneAnswer.of(
              policyDirectoryService.answer(request.message(), subject, decision),
              "policy_directory",
              "policy_directory_api");
      case "document_extraction" -> documentExtraction(request, subject, decision);
      case "neo4j_direct" -> neo4jDirect(request, subject, decision);
      case "eligibility" ->
          eligibilityLaneService.answer(request.message(), subject, decision);
      case "vector", "full_rag" ->
          fullRagLaneService.answer(request.message(), request.mode(), subject);
      default -> null;
    };
  }

  /**
   * Python records me-intents as {@code path=eligibility} + {@code intent_id=me.*} for OpenSLO /
   * golden parity (not {@code path=me}).
   */
  private LaneAnswer me(ChatRequest request, Subject subject, RouterDecision decision) {
    MeIntentResult result = meIntentService.answer(decision, request.message(), subject);
    return LaneAnswer.of(result.answer(), "eligibility", "formatter", result.intentId());
  }

  private LaneAnswer documentExtraction(
      ChatRequest request, Subject subject, RouterDecision decision) {
    DocumentExtractionResult result =
        documentExtractionService.answer(request.message(), subject, decision);
    return LaneAnswer.of(
        result.answer(), "document_extraction", "formatter", result.intentId());
  }

  private LaneAnswer neo4jDirect(ChatRequest request, Subject subject, RouterDecision decision) {
    Neo4jDirectResult result =
        neo4jDirectService.answer(request.message(), request.mode(), subject, decision);
    return LaneAnswer.neo4j(
        result.answer(),
        result.intentId(),
        result.cypher(),
        result.graphRows(),
        result.cypherProvenance());
  }
}
