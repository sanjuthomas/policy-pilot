from __future__ import annotations

import pytest
from chat_application.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    SourceHit,
)
from pydantic import ValidationError


class TestChatMessage:
    def test_valid_roles(self) -> None:
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatMessage(role="system", content="nope")  # type: ignore[arg-type]


class TestChatRequest:
    def test_defaults(self) -> None:
        req = ChatRequest(message="What happened today?")
        assert req.history == []
        assert req.mode == "events"

    def test_rejects_empty_message(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_accepts_mode_and_history(self) -> None:
        req = ChatRequest(
            message="Count alerts",
            history=[ChatMessage(role="user", content="prior")],
            mode="instructions",
        )
        assert req.mode == "instructions"
        assert len(req.history) == 1


class TestSourceHit:
    def test_minimal_fields(self) -> None:
        hit = SourceHit(score=1.0, sources=["vector"], summary="summary")
        assert hit.event_id is None
        assert hit.instruction_id is None

    def test_full_payload(self) -> None:
        hit = SourceHit(
            event_id="evt-1",
            instruction_id="inst-1",
            score=0.75,
            sources=["vector", "bm25"],
            summary="Approved",
            merged={"action": "APPROVE"},
            security_event={"event_id": "evt-1"},
        )
        assert hit.merged["action"] == "APPROVE"


class TestChatResponse:
    def test_response_shape(self) -> None:
        resp = ChatResponse(
            answer="Two alerts.",
            sources=[
                SourceHit(score=0.5, sources=["neo4j"], summary="alert"),
            ],
            cypher="MATCH (e) RETURN e LIMIT 1",
            graph_rows=[{"total": 2}],
            retrieval_ms=12.3,
            generation_ms=45.6,
        )
        assert resp.answer == "Two alerts."
        assert resp.graph_rows[0]["total"] == 2
