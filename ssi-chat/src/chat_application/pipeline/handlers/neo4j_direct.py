from __future__ import annotations

from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatResponse
from chat_application.observability.routing import (
    cypher_provenance_for_direct_intent,
    finalize_chat_response,
)
from chat_application.pipeline.handlers.base import HandlerContext

# Dedicated tool/skill/me paths must not be stolen by Neo4j direct.
_SKIP_DIRECT_PATHS = frozenset(
    {
        "skill",
        "me",
        "policy_summary",
        "policy_directory",
        "person_permissions",
        "eligibility",
    }
)


class Neo4jDirectHandler:
    """Latency fast-path: YAML + planned Cypher formatters (not primary NLU)."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        if ctx.path in _SKIP_DIRECT_PATHS:
            return None

        direct = await ctx.service._try_neo4j_direct_answer(ctx.message, mode=ctx.mode)
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
        )
