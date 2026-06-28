"""Tests for InstructionSecurityEventPipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from etl.instruction_security_event_pipeline import InstructionSecurityEventPipeline


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
    qdrant = MagicMock()
    qdrant.ensure_collection = MagicMock()
    qdrant.upsert = MagicMock()

    pipeline = InstructionSecurityEventPipeline(
        neo4j_writer=neo4j,
        ollama_client=ollama,
        qdrant_store=qdrant,
    )
    event = _security_event()
    await pipeline.process_instruction_security_event(event)

    neo4j.upsert.assert_awaited_once()
    ollama.warmup.assert_awaited_once()
    qdrant.upsert.assert_called_once()


async def test_process_approve_patches_authorization():
    neo4j = AsyncMock()
    ollama = AsyncMock()
    ollama.dimension = 2
    ollama.embed = AsyncMock(return_value=[0.5, 0.5])
    qdrant = MagicMock()
    qdrant.patch_instruction_state_authorization = MagicMock()

    pipeline = InstructionSecurityEventPipeline(
        neo4j_writer=neo4j,
        ollama_client=ollama,
        qdrant_store=qdrant,
    )
    pipeline._qdrant_ready = True

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

    qdrant.patch_instruction_state_authorization.assert_called_once_with(
        "instr-1",
        approved_at="2024-06-01",
        authorization_summary="approved by manager",
        authorization_basis=["role-match"],
    )
