from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from chat_application.neo4j_formatters import (
    format_instruction_creator_by_id,
    format_instruction_status_by_id,
    format_payment_creator_by_id,
)
from chat_application.neo4j_intents import (
    build_match_context,
    match_neo4j_direct_intent,
    try_neo4j_direct_answer,
)


class TestNeo4jDirectMatching:
    def test_matches_creator_by_instruction_id(self) -> None:
        question = "Who created 20260703-FICC-I-1?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.creator_by_id"
        assert match.formatter_name == "instruction_creator_by_id"
        assert "instruction_detail" in match.planned[0][0]

    def test_matches_creator_by_instruction_id_in_events_mode(self) -> None:
        question = "Who created 20260703-FICC-I-1?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "instruction.creator_by_id"

    def test_matches_creator_by_payment_id(self) -> None:
        question = "Who created 20260704-FICC-P-1?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.creator_by_id"
        assert match.formatter_name == "payment_creator_by_id"
        assert "payment_detail" in match.planned[0][0]

    def test_matches_creator_by_payment_id_in_events_mode(self) -> None:
        question = "Who created 20260704-FICC-P-1?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "payment.creator_by_id"

    def test_payment_creator_and_approver_beats_creator_only(self) -> None:
        question = "Who created 20260704-FICC-P-1 and who approved it?"
        match = match_neo4j_direct_intent(question, mode="payments")
        assert match is not None
        assert match.intent_id == "payment.creator_and_approver_by_id"

    def test_creator_and_approver_beats_creator_only(self) -> None:
        question = "Who created 20260703-FICC-I-1 and who approved it?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.creator_and_approver_by_id"

    def test_status_by_id(self) -> None:
        question = "What is the status of 20260703-FICC-I-1?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.status_by_id"

    def test_mutual_approval(self) -> None:
        question = "Are there any mutual approval cases?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is not None
        assert match.intent_id == "instruction.mutual_approval"

    def test_cross_entity_reciprocal_approval_events_mode(self) -> None:
        question = (
            "Are there cases where one user approved another user's instruction, "
            "and that same other user created a payment on that instruction that "
            "the first user then approved?"
        )
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "instruction.cross_entity_reciprocal_approval"
        assert match.planned[0][0] == "cross_entity_reciprocal_approval"
        assert "instruction_id AS instruction_id" in match.planned[0][1]

    def test_alerts_today_yaml_intent(self) -> None:
        question = "How many ALERT events happened today?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is not None
        assert match.intent_id == "events.alerts_today_count"

    def test_payment_alerts_today_uses_planned_graph_not_yaml(self) -> None:
        question = "How many payment ALERT events happened today?"
        match = match_neo4j_direct_intent(question, mode="events")
        assert match is None
        from chat_application.neo4j_intents import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="events")
        assert planned is not None
        assert "e.payment_id IS NOT NULL" in planned.planned[0][1]

    def test_planned_graph_count_single_use_via_direct_path(self) -> None:
        question = "How many single use instructions are there?"
        match = match_neo4j_direct_intent(question, mode="instructions")
        assert match is None
        from chat_application.neo4j_intents import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="instructions")
        assert planned is not None
        assert planned.intent_id == "planned_graph"
        assert "v.instruction_type = 'SINGLE_USE'" in planned.planned[0][1]
        assert "v.status = 'SINGLE_USE'" not in planned.planned[0][1]

    def test_planned_graph_group_by_status_via_direct_path(self) -> None:
        question = "Can you group instructions by status?"
        from chat_application.neo4j_intents import match_planned_graph_intent

        planned = match_planned_graph_intent(question, mode="instructions")
        assert planned is not None
        assert planned.intent_id == "planned_graph"
        assert planned.planned[0][0] == "facet_aggregate"

    def test_no_match_for_vague_question(self) -> None:
        assert match_neo4j_direct_intent("Tell me about instructions", mode="instructions") is None

    def test_build_match_context_extracts_instruction_id(self) -> None:
        context = build_match_context("Who created 20260703-FICC-I-1?")
        assert context["instruction_ids"] == ["20260703-FICC-I-1"]

    def test_build_match_context_extracts_payment_id(self) -> None:
        context = build_match_context("Who created 20260704-FICC-P-1?")
        assert context["payment_ids"] == ["20260704-FICC-P-1"]

    def test_build_match_context_extracts_user_id(self) -> None:
        context = build_match_context("Which instructions did mo-100 create?")
        assert context["user_id"] == "mo-100"


class TestNeo4jDirectFormatters:
    def test_format_creator_by_id(self) -> None:
        answer = format_instruction_creator_by_id(
            "Who created 20260703-FICC-I-1?",
            [{"instruction_id": "20260703-FICC-I-1", "creator_display": "Walsh, Patricia (mo-010)"}],
        )
        assert answer is not None
        assert "20260703-FICC-I-1" in answer
        assert "Walsh, Patricia (mo-010)" in answer

    def test_format_status_by_id(self) -> None:
        answer = format_instruction_status_by_id(
            "status?",
            [{"instruction_id": "20260703-FICC-I-1", "status": "DRAFT", "owning_lob": "FICC"}],
        )
        assert answer is not None
        assert "DRAFT" in answer
        assert "FICC" in answer

    def test_format_payment_creator_by_id(self) -> None:
        answer = format_payment_creator_by_id(
            "Who created 20260704-FICC-P-1?",
            [{"payment_id": "20260704-FICC-P-1", "creator_display": "Rodriguez, Emily (pay-101)"}],
        )
        assert answer is not None
        assert "20260704-FICC-P-1" in answer
        assert "Rodriguez, Emily (pay-101)" in answer


class TestNeo4jDirectExecution:
    @pytest.mark.asyncio
    async def test_try_neo4j_direct_answer_creator(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "instruction_id": "20260703-FICC-I-1",
                    "creator_display": "Walsh, Patricia (mo-010)",
                }
            ]
        )
        result = await try_neo4j_direct_answer(
            neo4j,
            "Who created 20260703-FICC-I-1?",
            mode="instructions",
        )
        assert result is not None
        assert "Walsh, Patricia (mo-010)" in result.answer
        assert result.intent_id == "instruction.creator_by_id"
        neo4j.run_cypher.assert_awaited()

    @pytest.mark.asyncio
    async def test_try_neo4j_direct_answer_payment_creator(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "payment_id": "20260704-FICC-P-1",
                    "creator_display": "Rodriguez, Emily (pay-101)",
                }
            ]
        )
        result = await try_neo4j_direct_answer(
            neo4j,
            "Who created 20260704-FICC-P-1?",
            mode="payments",
        )
        assert result is not None
        assert "Rodriguez, Emily (pay-101)" in result.answer
        assert result.intent_id == "payment.creator_by_id"
        neo4j.run_cypher.assert_awaited()

    @pytest.mark.asyncio
    async def test_try_neo4j_direct_answer_single_use_count(self) -> None:
        neo4j = AsyncMock()
        neo4j.run_cypher = AsyncMock(return_value=[{"total": 2}])
        result = await try_neo4j_direct_answer(
            neo4j,
            "How many single use instructions are there?",
            mode="instructions",
        )
        assert result is not None
        assert "2" in result.answer
        assert result.intent_id == "planned_graph"
        neo4j.run_cypher.assert_awaited()


class TestRagNeo4jDirectEarlyExit:
    @pytest.mark.asyncio
    async def test_ask_uses_neo4j_direct_without_llm(
        self, rag_service, mock_ml_client, mock_multimodal, mock_neo4j
    ) -> None:
        mock_neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "instruction_id": "20260703-FICC-I-1",
                    "creator_display": "Walsh, Patricia (mo-010)",
                }
            ]
        )
        mock_multimodal.search_vector = AsyncMock(return_value=[])
        mock_multimodal.search_bm25 = AsyncMock(return_value=[])
        mock_ml_client.embed = AsyncMock(return_value=[0.1, 0.2])
        mock_ml_client.synthesize_answer = AsyncMock(return_value="should not be called")

        response = await rag_service.ask(
            "Who created 20260703-FICC-I-1?",
            [],
            mode="events",
        )

        assert "Walsh, Patricia (mo-010)" in response.answer
        assert response.generation_ms == 0.0
        mock_ml_client.synthesize_answer.assert_not_called()
        mock_ml_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_ask_uses_neo4j_direct_for_payment_creator(
        self, rag_service, mock_ml_client, mock_multimodal, mock_neo4j
    ) -> None:
        mock_neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "payment_id": "20260704-FICC-P-1",
                    "creator_display": "Rodriguez, Emily (pay-101)",
                }
            ]
        )
        mock_multimodal.search_vector = AsyncMock(return_value=[])
        mock_multimodal.search_bm25 = AsyncMock(return_value=[])
        mock_ml_client.embed = AsyncMock(return_value=[0.1, 0.2])
        mock_ml_client.synthesize_answer = AsyncMock(return_value="should not be called")

        response = await rag_service.ask(
            "Who created 20260704-FICC-P-1?",
            [],
            mode="payments",
        )

        assert "Rodriguez, Emily (pay-101)" in response.answer
        assert response.generation_ms == 0.0
        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.intent_id == "payment.creator_by_id"
        mock_ml_client.synthesize_answer.assert_not_called()
        mock_ml_client.embed.assert_not_called()
