from __future__ import annotations

from chat_application.auth.retrieval_scope import allowed_retrieval_lobs
from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatResponse
from chat_application.observability.routing import (
    cypher_provenance_for_direct_intent,
    finalize_chat_response,
)
from chat_application.pipeline.handlers.base import HandlerContext


class Neo4jDirectHandler:
    """Path-owned deterministic fast path: YAML + planned Cypher formatters.

    Only runs when ``RouterDecision.path == neo4j_direct`` (path is law).
    No longer steals investigate turns that routed to graph/vector/hybrid.
    """

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        if ctx.path != "neo4j_direct":
            return None

        direct = await ctx.service._try_neo4j_direct_answer(
            ctx.message,
            mode=ctx.mode,
            allowed_lobs=allowed_retrieval_lobs(ctx.subject),
        )
        if direct is None:
            return None

        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=format_chat_response(direct.answer),
            cypher=direct.cypher,
            graph_rows=direct.graph_rows,
            retrieval_ms=ctx.elapsed_ms(),
            generation_ms=0.0,
            path="neo4j_direct",
            cypher_provenance=cypher_provenance_for_direct_intent(
                direct.intent_id,
                source=direct.source,
            ),
            answer_synthesis="formatter",
            intent_id=direct.intent_id,
            requested_path=ctx.path,
        )
