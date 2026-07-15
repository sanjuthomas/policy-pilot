from __future__ import annotations

from chat_application.formatting.response import format_chat_response
from chat_application.models import ChatResponse
from chat_application.observability.routing import finalize_chat_response
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.handlers.gates import DenialReason, denial_message


class DenialHandler:
    """Capability / mode fence refusal (no fallthrough)."""

    def __init__(self, reason: DenialReason) -> None:
        self._reason = reason

    async def handle(self, ctx: HandlerContext) -> ChatResponse:
        answer, path = denial_message(self._reason)
        return finalize_chat_response(
            ctx.message,
            ctx.mode,
            answer=format_chat_response(answer),
            retrieval_ms=0.0,
            generation_ms=ctx.elapsed_ms(),
            path=path,  # type: ignore[arg-type]
            cypher_provenance="none",
            answer_synthesis="formatter",
            intent_id=f"gate.{self._reason.value}",
        )
