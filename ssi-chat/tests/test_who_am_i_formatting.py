"""Cross-layer coverage for who-am-I answer formatting through the me handler path."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat_application.auth.capabilities import capabilities_for
from chat_application.auth.subject import Subject
from chat_application.formatting.response import format_chat_response
from chat_application.me.who_am_i import answer_who_am_i
from chat_application.pipeline.handlers.base import HandlerContext
from chat_application.pipeline.handlers.me import MeIntentHandler
from chat_application.pipeline.models import RouterDecision


def _subject() -> Subject:
    return Subject(
        user_id="pay-203",
        given_name="Anna",
        family_name="Kowalski",
        title="Vice President",
        roles=["PAYMENT_CREATOR", "FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        lob="FICC",
        covering_lobs=["FX"],
        supervisor_id="pay-201",
    )


def _assert_title_case_labels_intact(answer: str) -> None:
    assert "**Title:**" in answer or "| Title" in answer
    assert "**Roles:**" in answer or "| Roles" in answer
    assert "**Groups:**" in answer or "| Groups" in answer
    assert "**Supervisor:**" in answer or "| Supervisor" in answer
    for mangled in ("Itle", "Oles", "Roups", "Upervisor"):
        assert mangled not in answer


class TestWhoAmIFormatting:
    """Who-am-I bullets must keep Title-case labels through ``format_chat_response``."""

    def test_who_am_i_through_response_formatter(self) -> None:
        raw = answer_who_am_i(_subject()).answer
        formatted = format_chat_response(raw)
        assert formatted == raw
        _assert_title_case_labels_intact(formatted)

    @pytest.mark.asyncio
    async def test_me_intent_handler_preserves_labels(self) -> None:
        subject = _subject()
        caps = capabilities_for(subject)
        ctx = HandlerContext(
            service=MagicMock(),
            message="Who am I?",
            history=[],
            mode="all",
            decision=RouterDecision(path="me", me_kind="who_am_i"),
            subject=subject,
            capabilities=caps,
            bearer_token="token",
            session_id="sess",
            started=time.perf_counter(),
        )
        response = await MeIntentHandler().handle(ctx)
        assert response is not None
        assert response.routing is not None
        assert response.routing.intent_id == "me.who_am_i"
        _assert_title_case_labels_intact(response.answer)
        assert "Vice President" in response.answer
        assert "pay-201" in response.answer

    @pytest.mark.asyncio
    async def test_ask_who_am_i_preserves_labels(
        self, rag_service, mock_ml_client, mock_vector_search, mock_neo4j
    ) -> None:
        subject = _subject()
        mock_ml_client.route_query = AsyncMock(
            return_value=RouterDecision(path="me", me_kind="who_am_i")
        )
        mock_neo4j.run_cypher = AsyncMock(return_value=[])
        mock_vector_search.search_vector = AsyncMock(return_value=[])

        response = await rag_service.ask(
            "Who am I?",
            [],
            mode="all",
            subject=subject,
        )

        assert response.routing is not None
        assert response.routing.path == "me" or response.routing.intent_id == "me.who_am_i"
        _assert_title_case_labels_intact(response.answer)
        mock_ml_client.synthesize_answer.assert_not_called()
