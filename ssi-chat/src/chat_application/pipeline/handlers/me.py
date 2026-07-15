from __future__ import annotations

from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatResponse
from chat_application.observability.routing import finalize_chat_response
from chat_application.pipeline.handlers.base import HandlerContext


class MeIntentHandler:
    """Logged-in subject me-intents (who am I, permissions, waiting for me, …)."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        from chat_application.me import me_intent_from_router, try_me_intent

        if ctx.subject is None:
            return None

        intent = me_intent_from_router(ctx.decision, ctx.message)
        result = await try_me_intent(ctx.message, subject=ctx.subject, intent=intent)
        if result is None:
            return None

        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=format_chat_response(result.answer),
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="formatter",
            intent_id=result.intent_id,
        )
