package com.sanjuthomas.policypilot.service;

import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.observability.ChatAnswerFinalizer;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.IntentRouter;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

/**
 * Chat entrypoint: route → {@link ChatPathDispatcher} → {@link ChatAnswerFinalizer}. Domain work
 * lives in path lane services.
 */
@Service
public class ChatService {

  private static final String UNSUPPORTED_ANSWER =
      "ssi-chat-j answers payment/instruction eligibility, document extraction "
          + "(show payment/instruction by id), policy-directory, policy-summary, "
          + "me-centric questions, and neo4j_direct graph answers "
          + "(ALERT counts/lists, entity status/creator by id). ";

  private final IntentRouter intentRouter;
  private final ChatPathDispatcher pathDispatcher;
  private final ChatAnswerFinalizer answerFinalizer;

  public ChatService(
      IntentRouter intentRouter,
      ChatPathDispatcher pathDispatcher,
      ChatAnswerFinalizer answerFinalizer) {
    this.intentRouter = intentRouter;
    this.pathDispatcher = pathDispatcher;
    this.answerFinalizer = answerFinalizer;
  }

  public ChatResponse ask(ChatRequest request, Subject subject) {
    long routeStartNs = System.nanoTime();
    RouterDecision decision = intentRouter.route(request.message());
    double routeMs = (System.nanoTime() - routeStartNs) / 1_000_000.0;
    String requestedPath = decision.getPath();

    long retrievalStartNs = System.nanoTime();
    LaneAnswer lane = pathDispatcher.dispatch(decision, request, subject);
    double laneMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;

    // Me lane records path=eligibility for OpenSLO parity; do not treat router "me" as requested.
    String effectiveRequested = "me".equals(requestedPath) ? null : requestedPath;

    if (lane == null) {
      return finalize(
          request,
          UNSUPPORTED_ANSWER + "Routed as path=" + decision.getPath() + ".",
          decision.getPath(),
          "stub",
          effectiveRequested,
          routeMs + laneMs,
          0.0,
          null,
          null,
          null,
          "none");
    }

    // Parity with Python neo4j_direct / document_extraction: formatter answers report
    // generation_ms=0 (deterministic quality gate max is 100ms); router+lane → retrieval_ms.
    boolean formatterOnly = "formatter".equals(lane.synthesis());
    double retrievalMs = formatterOnly ? routeMs + laneMs : laneMs;
    double generationMs = formatterOnly ? 0.0 : routeMs;

    return finalize(
        request,
        lane.answer(),
        lane.recordedPath(),
        lane.synthesis(),
        effectiveRequested,
        retrievalMs,
        generationMs,
        lane.intentId(),
        lane.cypher(),
        lane.graphRows(),
        lane.cypherProvenance());
  }

  private ChatResponse finalize(
      ChatRequest request,
      String answerText,
      String path,
      String synthesis,
      String requestedPath,
      double retrievalMs,
      double generationMs,
      String intentId,
      String cypher,
      List<Map<String, Object>> graphRows,
      String cypherProvenance) {
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
        generationMs,
        intentId,
        cypher,
        graphRows,
        cypherProvenance);
  }
}
