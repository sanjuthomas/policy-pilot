from __future__ import annotations

import logging
from typing import Any

from chat_application.auth.retrieval_scope import allowed_retrieval_lobs
from chat_application.config import settings
from chat_application.formatting.response import format_chat_response
from chat_application.graph.cypher import extract_entity_ids, extract_uuids
from chat_application.models import ChatMessage, ChatResponse, SearchMode
from chat_application.observability.routing import (
    AnswerSynthesis,
    finalize_chat_response,
)
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.retrieve import execute_selective_retrieval

logger = logging.getLogger(__name__)

_GRAPH_UNAVAILABLE_ANSWER = (
    "I couldn't retrieve Neo4j graph results for this question "
    "(query planning or execution failed). "
    "I won't invent an answer without graph evidence — please rephrase, "
    "include a specific entity id, or try again shortly."
)


class InvestigateHandler:
    """Read-only investigation: selective retrieve + synthesize."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse:
        execution_strategy = ctx.decision.retrieval_strategy
        if execution_strategy == "eligibility" or ctx.path == "neo4j_direct":
            # neo4j_direct miss fallthrough uses graph retrieve.
            execution_strategy = "graph"

        search_source = _search_source_for_mode(ctx.mode)
        event_ids = extract_uuids(ctx.message)
        entity_ids = extract_entity_ids(ctx.message)

        retrieval = await execute_selective_retrieval(
            ctx.service,
            message=ctx.message,
            mode=ctx.mode,
            strategy=execution_strategy,
            limit=settings.retrieval_limit,
            search_source=search_source,
            event_ids=event_ids,
            entity_ids=entity_ids,
            allowed_lobs=allowed_retrieval_lobs(ctx.subject),
        )
        retrieval_ms = ctx.elapsed_ms()

        graph_result = retrieval.graph_result
        graph_provenance = graph_result.get("cypher_provenance") or "none"
        if (
            execution_strategy == "graph"
            and graph_result.get("llm_rate_limited")
            and not graph_result.get("cypher")
            and not graph_result.get("rows")
        ):
            logger.warning(
                "short-circuiting for Gemini rate limit during graph planning "
                "(provenance=%s)",
                graph_provenance,
            )
            return _rate_limited_response(
                ctx.message,
                ctx.mode,
                retrieval_ms=retrieval_ms,
                cypher_provenance=graph_provenance,
            )
        if _should_short_circuit_graph_unavailable(execution_strategy, graph_result):
            logger.warning(
                "short-circuiting Gemini synthesis: graph strategy with unavailable graph "
                "(provenance=%s)",
                graph_provenance,
            )
            return finalize_chat_response(
                ctx.message,
                ctx.mode,
                answer=format_chat_response(_GRAPH_UNAVAILABLE_ANSWER),
                sources=[ctx.service._to_source(hit) for hit in retrieval.merged],
                cypher=graph_result.get("cypher"),
                graph_rows=retrieval.graph_rows,
                retrieval_ms=retrieval_ms,
                generation_ms=0.0,
                path="full_rag",
                cypher_provenance=graph_provenance,
                answer_synthesis="formatter",
                intent_id="graph.unavailable",
            )

        import time

        gen_started = time.perf_counter()
        try:
            answer, answer_synthesis = await _synthesize(
                ctx.service,
                ctx.message,
                ctx.history,
                mode=ctx.mode,
                entity_ids=entity_ids,
                merged=retrieval.merged,
                graph_result=graph_result,
            )
        except Exception as exc:
            from chat_application.gemini.errors import is_gemini_rate_limit_error

            if is_gemini_rate_limit_error(exc):
                logger.warning("Gemini rate-limited during answer synthesis: %s", exc)
                return _rate_limited_response(
                    ctx.message,
                    ctx.mode,
                    retrieval_ms=retrieval_ms,
                    cypher_provenance=graph_provenance,
                )
            raise
        generation_ms = (time.perf_counter() - gen_started) * 1000

        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=answer,
            sources=[ctx.service._to_source(hit) for hit in retrieval.merged],
            cypher=graph_result.get("cypher"),
            graph_rows=retrieval.graph_rows,
            retrieval_ms=retrieval_ms,
            generation_ms=max(generation_ms, 0.0),
            path="full_rag",
            cypher_provenance=graph_provenance,
            answer_synthesis=answer_synthesis,
        )


def should_short_circuit_graph_unavailable(
    strategy: str,
    graph_result: dict[str, Any],
) -> bool:
    """Pure graph routes must not invent answers when Neo4j produced no evidence."""
    return _should_short_circuit_graph_unavailable(strategy, graph_result)


def _should_short_circuit_graph_unavailable(
    strategy: str,
    graph_result: dict[str, Any],
) -> bool:
    if strategy != "graph":
        return False
    if graph_result.get("cypher") or graph_result.get("rows"):
        return False
    return True


def _search_source_for_mode(mode: SearchMode) -> str | None:
    if mode == "events":
        return "security_events"
    if mode == "instructions":
        return "instruction_state"
    if mode == "payments":
        return "payment"
    if mode == "policies":
        return None
    return None


def _rate_limited_response(
    message: str,
    mode: SearchMode,
    *,
    retrieval_ms: float,
    cypher_provenance: str = "none",
    path: str = "full_rag",
) -> ChatResponse:
    from chat_application.gemini.errors import (
        GEMINI_RATE_LIMIT_ANSWER,
        GEMINI_RATE_LIMIT_RETRY_SECONDS,
        gemini_rate_limit_intent_id,
    )

    return finalize_chat_response(
        message,
        mode,
        answer=format_chat_response(GEMINI_RATE_LIMIT_ANSWER),
        sources=[],
        cypher=None,
        graph_rows=[],
        retrieval_ms=retrieval_ms,
        generation_ms=0.0,
        path=path,  # type: ignore[arg-type]
        cypher_provenance=cypher_provenance,  # type: ignore[arg-type]
        answer_synthesis="formatter",
        intent_id=gemini_rate_limit_intent_id(),
        retry_after_seconds=GEMINI_RATE_LIMIT_RETRY_SECONDS,
    )


async def _synthesize(
    service: Any,
    message: str,
    history: list[ChatMessage],
    *,
    mode: SearchMode,
    entity_ids: list[str],
    merged: list[Any],
    graph_result: dict[str, Any],
) -> tuple[str, AnswerSynthesis]:
    from chat_application.formatting.dispatch import format_planned_graph_answer
    from chat_application.graph.cypher import plan_graph_queries
    from chat_application.rag import (
        _is_instruction_approval_question,
        _is_payment_approval_question,
    )

    context = service._build_context(
        merged,
        graph_result["rows"],
        graph_result.get("cypher"),
        graph_unavailable=graph_result.get("graph_unavailable", False),
        mode=mode,
    )
    chat_history = [{"role": item.role, "content": item.content} for item in history[-8:]]

    answer: str | None = None
    answer_synthesis: AnswerSynthesis = "gemini_full"

    if _is_instruction_approval_question(message, mode):
        answer = await service._synthesize_instruction_approval_answer(
            message, entity_ids, merged, graph_result["rows"]
        )
        if answer is not None:
            answer_synthesis = "gemini_why_only"
    if answer is None and _is_payment_approval_question(message, mode):
        answer = await service._synthesize_payment_approval_answer(
            message, entity_ids, merged, graph_result["rows"]
        )
        if answer is not None:
            answer_synthesis = "gemini_why_only"
    if answer is None:
        planned = graph_result.get("planned") or plan_graph_queries(message, mode=mode)
        if planned:
            answer = format_planned_graph_answer(
                message,
                mode=mode,
                planned=planned,
                rows=graph_result["rows"],
            )
            if answer is not None:
                answer_synthesis = "formatter"
    if answer is None:
        answer = await service.ml_client.synthesize_answer(
            message, context, chat_history, mode=mode
        )
        answer_synthesis = "gemini_full"

    return format_chat_response(answer), answer_synthesis
