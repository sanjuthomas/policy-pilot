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
