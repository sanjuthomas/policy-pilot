package com.sanjuthomas.policypilot.service;

import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.gemini.GeminiErrors;
import com.sanjuthomas.policypilot.observability.ChatAnswerFinalizer;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.IntentRouter;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Chat entrypoint: route → {@link ChatPathDispatcher} → {@link ChatAnswerFinalizer}. Domain work
 * lives in path lane services.
 */
@Service
public class ChatService {

  private static final Logger log = LoggerFactory.getLogger(ChatService.class);

  private static final String UNSUPPORTED_ANSWER =
      "ssi-chat-j answers payment/instruction eligibility, document extraction "
          + "(show payment/instruction by id), policy-directory, policy-summary, "
          + "person-permissions, me-centric questions, neo4j_direct graph answers "
          + "(ALERT counts/lists, entity status/creator by id), payment mutation skills "
          + "(create/submit/approve/cancel), and vector/full_rag "
          + "security-event narratives. ";

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
    long askStartNs = System.nanoTime();
    String pathHint = "full_rag";
    try {
      long routeStartNs = System.nanoTime();
      RouterDecision decision = intentRouter.route(request.message());
      double routeMs = (System.nanoTime() - routeStartNs) / 1_000_000.0;
      String requestedPath = decision.getPath();
      if (requestedPath != null && !requestedPath.isBlank()) {
        pathHint = requestedPath;
      }

      long retrievalStartNs = System.nanoTime();
      LaneAnswer lane = pathDispatcher.dispatch(decision, request, subject);
      double laneMs = (System.nanoTime() - retrievalStartNs) / 1_000_000.0;

      // Me lane records path=eligibility for OpenSLO parity; do not treat router "me" as requested.
      // Vector lane records path=full_rag; treat router vector as matching executed path.
      String effectiveRequested = "me".equals(requestedPath) ? null : requestedPath;
      if ("vector".equals(effectiveRequested)
          && lane != null
          && "full_rag".equals(lane.recordedPath())) {
        effectiveRequested = null;
      }

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
            "none",
            List.of(),
            List.of(),
            null);
      }

      // Parity with Python neo4j_direct / document_extraction: formatter answers report
      // generation_ms=0 (deterministic quality gate max is 100ms); router+lane → retrieval_ms.
      // Gemini synthesis lanes report lane time as generation_ms (embed+search+synth).
      boolean formatterOnly = "formatter".equals(lane.synthesis());
      boolean geminiSynth =
          "gemini_full".equals(lane.synthesis()) || "gemini_why_only".equals(lane.synthesis());
      double retrievalMs;
      double generationMs;
      if (formatterOnly) {
        retrievalMs = routeMs + laneMs;
        generationMs = 0.0;
      } else if (geminiSynth) {
        retrievalMs = routeMs;
        generationMs = laneMs;
      } else {
        retrievalMs = laneMs;
        generationMs = routeMs;
      }

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
          lane.cypherProvenance(),
          lane.sources(),
          lane.skillActivities(),
          lane.skillConfirmation());
    } catch (RuntimeException ex) {
      if (GeminiErrors.isRateLimit(ex)) {
        double elapsedMs = (System.nanoTime() - askStartNs) / 1_000_000.0;
        log.warn(
            "Gemini rate-limited during chat (path_hint={}): {}", pathHint, ex.toString());
        if (answerFinalizer == null) {
          return ChatResponse.of(GeminiErrors.RATE_LIMIT_ANSWER, null);
        }
        return answerFinalizer.rateLimited(
            request.message(), request.mode(), pathHint, elapsedMs);
      }
      throw ex;
    }
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
      String cypherProvenance,
      List<SourceHit> sources,
      List<String> skillActivities,
      Map<String, Object> skillConfirmation) {
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
        cypherProvenance,
        sources,
        skillActivities,
        skillConfirmation);
  }
}
