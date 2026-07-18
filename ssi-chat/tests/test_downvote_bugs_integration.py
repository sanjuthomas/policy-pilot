"""Cross-layer integration coverage for production downvote regressions.

These tests exercise handler / ask paths end-to-end (intent → Cypher or me answer →
``format_chat_response``), not isolated unit helpers alone.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat_application.auth.capabilities import capabilities_for
from chat_application.auth.subject import Subject
from chat_application.formatting.response import format_chat_response
from chat_application.graph.direct import try_neo4j_direct_answer
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


class TestWhoAmIFormattingIntegration:
    """Downvote: Title/Roles/Groups/Supervisor rendered as Itle/Oles/Roups/Upervisor."""

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


class TestApprovedStandingInventoryIntegration:
    """Downvote: 'list approved standing instructions' ignored status or type."""

    @pytest.mark.asyncio
    async def test_try_neo4j_direct_applies_status_and_type_filters(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "instruction_id": "20260717-FICC-I-1",
                    "status": "APPROVED",
                    "instruction_type": "STANDING",
                    "owning_lob": "FICC",
                    "currency": "USD",
                    "wire_scope": "DOMESTIC",
                    "creator_display": "Walsh, Patricia (mo-010)",
                    "approver_display": "Nguyen, Caroline (ficc-500)",
                    "approved_at": "2026-07-17T10:00:00",
                }
            ]
        )
        question = "can you list all approved standing instructions?"
        result = await try_neo4j_direct_answer(neo4j, question, mode="instructions")
        assert result is not None
        assert result.intent_id == "instruction.list_standing"
        cypher = neo4j.run_cypher.await_args.args[0]
        assert "status = 'APPROVED'" in cypher
        assert "instruction_type = 'STANDING'" in cypher
        assert "20260717-FICC-I-1" in result.answer
        assert "APPROVED" in result.answer
        # Type is enforced in Cypher; inventory table may omit the Type column.

    @pytest.mark.asyncio
    async def test_ask_approved_standing_list_filters_and_formats(
        self, rag_service, mock_ml_client, mock_vector_search, mock_neo4j
    ) -> None:
        mock_neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "instruction_id": "20260717-FICC-I-1",
                    "status": "APPROVED",
                    "instruction_type": "STANDING",
                    "owning_lob": "FICC",
                    "currency": "USD",
                    "wire_scope": "DOMESTIC",
                    "creator_display": "Walsh, Patricia (mo-010)",
                    "approver_display": "Nguyen, Caroline (ficc-500)",
                    "approved_at": "2026-07-17T10:00:00",
                },
                {
                    "instruction_id": "20260717-FX-I-2",
                    "status": "APPROVED",
                    "instruction_type": "STANDING",
                    "owning_lob": "FX",
                    "currency": "USD",
                    "wire_scope": "DOMESTIC",
                    "creator_display": "Chen, Sarah (mo-100)",
                    "approver_display": "Vasquez, Elena (ficc-300)",
                    "approved_at": "2026-07-17T11:00:00",
                },
            ]
        )
        mock_vector_search.search_vector = AsyncMock(return_value=[])
        mock_ml_client.synthesize_answer = AsyncMock(return_value="should not be called")

        response = await rag_service.ask(
            "can you list all approved standing instructions?",
            [],
            mode="instructions",
        )

        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.intent_id == "instruction.list_standing"
        cypher = mock_neo4j.run_cypher.await_args.args[0]
        assert "status = 'APPROVED'" in cypher
        assert "instruction_type = 'STANDING'" in cypher
        assert "20260717-FICC-I-1" in response.answer
        assert "20260717-FX-I-2" in response.answer
        assert "| Instruction ID" in response.answer or "Instruction ID" in response.answer
        mock_ml_client.synthesize_answer.assert_not_called()
