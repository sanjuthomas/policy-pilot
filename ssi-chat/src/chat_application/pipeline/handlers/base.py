from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from chat_application.auth.capabilities import ChatCapabilities
from chat_application.models import ChatMessage, ChatResponse, SearchMode
from chat_application.pipeline.models import RouterDecision

if TYPE_CHECKING:
    from chat_application.auth.subject import Subject
    from chat_application.rag import RagService


@dataclass(frozen=True)
class HandlerContext:
    """Shared request context for a single chat turn."""

    service: "RagService"
    message: str
    history: list[ChatMessage]
    mode: SearchMode
    decision: RouterDecision
    subject: "Subject | None"
    capabilities: ChatCapabilities
    bearer_token: str | None
    session_id: str | None
    started: float

    @property
    def path(self) -> str | None:
        return self.decision.path or self.decision.retrieval_strategy

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.started) * 1000


class ChatHandler(Protocol):
    """Lane handler: skills, tools, me, neo4j-direct, or investigate RAG."""

    async def handle(self, ctx: HandlerContext) -> ChatResponse | None:
        """Return a response, or None to fall through to the next handler."""
