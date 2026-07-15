from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from chat_application.auth.capabilities import ChatCapabilities, capabilities_for
from chat_application.models import ChatMessage, ChatResponse, SearchMode
from chat_application.pipeline.follow_up import expand_follow_up_question
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.handlers.investigate import (
    should_short_circuit_graph_unavailable,
)
from chat_application.pipeline.handlers.registry import resolve_and_handle
from chat_application.pipeline.route import route_question

if TYPE_CHECKING:
    from chat_application.auth.subject import Subject
    from chat_application.rag import RagService

logger = logging.getLogger(__name__)


def _capabilities_for_optional(subject: Subject | None) -> ChatCapabilities:
    """Unauthenticated/test contexts get investigation-only caps (no skills/tools)."""
    if subject is None:
        return ChatCapabilities(
            is_compliance=False,
            can_create_payment=False,
            can_approve_payment=False,
        )
    return capabilities_for(subject)


class RagPipelineOrchestrator:
    """Thin dispatch: route → capability/mode fence → lane handler."""

    def __init__(self, service: RagService) -> None:
        self._service = service

    async def ask(
        self,
        message: str,
        history: list[ChatMessage],
        *,
        mode: SearchMode = "events",
        bearer_token: str | None = None,
        session_id: str | None = None,
        subject: "Subject | None" = None,
    ) -> ChatResponse:
        started = time.perf_counter()
        message = expand_follow_up_question(message, history)
        decision = await route_question(self._service.ml_client, message, mode=mode)
        capabilities = _capabilities_for_optional(subject)

        ctx = HandlerContext(
            service=self._service,
            message=message,
            history=history,
            mode=mode,
            decision=decision,
            subject=subject,
            capabilities=capabilities,
            bearer_token=bearer_token,
            session_id=session_id,
            started=started,
        )
        return await resolve_and_handle(ctx)

    @staticmethod
    def _should_short_circuit_graph_unavailable(
        strategy: str,
        graph_result: dict[str, Any],
    ) -> bool:
        """Preserved for unit tests; implementation lives on investigate handler."""
        return should_short_circuit_graph_unavailable(strategy, graph_result)
