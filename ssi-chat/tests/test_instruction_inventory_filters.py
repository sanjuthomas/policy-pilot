"""Cross-layer coverage for instruction inventory status + type filters."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chat_application.graph.direct import try_neo4j_direct_answer


class TestInstructionInventoryStatusAndType:
    """List questions may combine lifecycle status and instruction_type filters."""

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
