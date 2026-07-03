"""Tests for InstructionSecurityEventPipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from etl.instruction_security_event_pipeline import InstructionSecurityEventPipeline
from etl.multimodal_write import MultimodalWrite


def _security_event(**overrides) -> dict:
    base = {
        "event_id": "sevt-1",
        "message": "approved",
        "resource": {"id": "instr-1", "version_number": 1},
        "event": {"action": "READ", "outcome": "ALLOW"},
        "instruction_snapshot": {
            "instruction_id": "instr-1",
            "status": "ACTIVE",
            "created_by": {"user_id": "c1"},
        },
    }
    base.update(overrides)
    return base


async def test_process_instruction_security_event():
    neo4j = AsyncMock()
    neo4j.upsert = AsyncMock()
    ollama = AsyncMock()
    ollama.dimension = 4
    ollama.warmup = AsyncMock()
    ollama.embed = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])
    multimodal = MagicMock()
    multimodal.ensure_indexes = AsyncMock()

    pipeline = InstructionSecurityEventPipeline(
        neo4j_writer=neo4j,
        ollama_client=ollama,
        multimodal_store=multimodal,
    )
    event = _security_event()
    await pipeline.process_instruction_security_event(event)

    neo4j.upsert.assert_awaited_once()
    ollama.warmup.assert_awaited_once()
    ollama.embed.assert_awaited_once()
    call_kwargs = neo4j.upsert.call_args.kwargs
    assert isinstance(call_kwargs["multimodal"], MultimodalWrite)
    assert call_kwargs["multimodal"].dense_vector == [0.1, 0.2, 0.3, 0.4]


async def test_process_approve_patches_authorization_in_same_tx():
    neo4j = AsyncMock()
    neo4j.upsert = AsyncMock()
    ollama = AsyncMock()
    ollama.dimension = 2
    ollama.embed = AsyncMock(side_effect=[[0.5, 0.5], [0.6, 0.6]])
    multimodal = MagicMock()
    multimodal.build_instruction_state_authorization_patch = AsyncMock(
        return_value=("doc-1", "patched search text", {"instruction_id": "instr-1"})
    )

    pipeline = InstructionSecurityEventPipeline(
        neo4j_writer=neo4j,
        ollama_client=ollama,
        multimodal_store=multimodal,
    )
    pipeline._multimodal_ready = True

    event = _security_event(
        event={"action": "APPROVE", "outcome": "ALLOW"},
        details={
            "authorization": {
                "summary": "approved by manager",
                "allow_basis": ["role-match"],
            }
        },
        instruction_snapshot={
            "instruction_id": "instr-1",
            "approved_at": "2024-06-01",
            "created_by": {"user_id": "c1"},
        },
    )
    await pipeline.process_instruction_security_event(event)

    multimodal.build_instruction_state_authorization_patch.assert_awaited_once_with(
        "instr-1",
        approved_at="2024-06-01",
        authorization_summary="approved by manager",
        authorization_basis=["role-match"],
    )
    assert ollama.embed.await_count == 2
    extra = neo4j.upsert.call_args.kwargs["extra_multimodal"]
    assert len(extra) == 1
    assert extra[0].search_text == "patched search text"
