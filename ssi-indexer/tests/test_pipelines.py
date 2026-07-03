"""Tests for pipeline orchestration with mocked backends."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from etl.instruction_pipeline import InstructionPipeline
from etl.payment_pipeline import PaymentFactPipeline, PaymentSecurityEventPipeline


@pytest.fixture
def mock_neo4j() -> AsyncMock:
    writer = AsyncMock()
    writer.upsert_instruction_fact = AsyncMock()
    writer.upsert_payment_security_event = AsyncMock()
    writer.upsert_payment_fact = AsyncMock()
    return writer


@pytest.fixture
def mock_ollama() -> AsyncMock:
    client = AsyncMock()
    client.dimension = 3
    client.warmup = AsyncMock()
    client.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return client


@pytest.fixture
def mock_multimodal() -> MagicMock:
    store = MagicMock()
    store.ensure_indexes = AsyncMock()
    store.get_instruction_state_payload = AsyncMock(return_value=None)
    store.upsert_instruction_state = AsyncMock()
    store.upsert_payment_point = AsyncMock()
    return store


def _instruction_fact(**overrides) -> dict:
    base = {
        "instruction_id": "instr-merge",
        "version_number": 2,
        "action": "UPDATE",
        "timestamp": "2024-01-01T00:00:00Z",
        "actor_user_id": "actor-1",
        "actor_given_name": "Act",
        "actor_family_name": "Or",
        "instruction_snapshot": {
            "status": "PENDING",
            "instruction_type": "WIRE",
            "owning_lob": "LOB1",
            "created_by": {"user_id": "c1", "given_name": "C", "family_name": "One"},
            "approved_by": {"user_id": "a1", "given_name": "A", "family_name": "Two"},
            "rejected_by": {"user_id": "r1", "given_name": "R", "family_name": "Three"},
        },
    }
    base.update(overrides)
    return base


async def test_instruction_pipeline_skips_missing_id(mock_neo4j, mock_ollama, mock_multimodal):
    pipeline = InstructionPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    await pipeline.process_instruction_fact({})
    mock_neo4j.upsert_instruction_fact.assert_not_called()


async def test_instruction_pipeline_processes_new_fact(mock_neo4j, mock_ollama, mock_multimodal):
    pipeline = InstructionPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    fact = _instruction_fact()
    await pipeline.process_instruction_fact(fact)

    mock_neo4j.upsert_instruction_fact.assert_awaited_once()
    call_kwargs = mock_neo4j.upsert_instruction_fact.call_args
    assert call_kwargs.args[0] == fact
    assert "multimodal" in call_kwargs.kwargs
    mock_ollama.warmup.assert_awaited_once()
    mock_multimodal.ensure_indexes.assert_awaited_once_with(3)
    mock_ollama.embed.assert_awaited_once()


async def test_instruction_pipeline_merges_existing_payload(mock_neo4j, mock_ollama, mock_multimodal):
    mock_multimodal.get_instruction_state_payload.return_value = {
        "authorization_summary": "prev summary",
        "authorization_basis": ["old-rule"],
        "approved_at": "2023-12-01",
        "approver_display": "Old Approver",
        "approver_user_id": "old-a",
        "rejector_display": "Old Rejector",
        "rejector_user_id": "old-r",
        "rejected_at": "2023-11-01",
        "rejection_reason": "old reason",
    }
    pipeline = InstructionPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    pipeline._multimodal_ready = True

    fact = _instruction_fact(
        action="UPDATE",
        instruction_snapshot={
            "status": "PENDING",
            "instruction_type": "WIRE",
            "owning_lob": "LOB1",
            "created_by": {"user_id": "c1", "given_name": "C", "family_name": "One"},
            "approved_by": {},
            "rejected_by": {},
        },
    )
    await pipeline.process_instruction_fact(fact)

    payload = mock_neo4j.upsert_instruction_fact.call_args.kwargs["multimodal"].payload
    assert payload["instruction_id"] == "instr-merge"
    assert payload["status"] == "PENDING"
    assert payload["authorization_summary"] == "prev summary"
    assert payload["authorization_basis"] == ["old-rule"]
    assert payload["approved_at"] == "2023-12-01"
    assert payload["approver_display"] == "Old Approver"
    assert payload["rejector_display"] == "Old Rejector"
    assert payload["rejection_reason"] == "old reason"


async def test_instruction_pipeline_approve_does_not_preserve_old_auth(mock_neo4j, mock_ollama, mock_multimodal):
    mock_multimodal.get_instruction_state_payload.return_value = {
        "authorization_summary": "stale",
        "authorization_basis": ["stale-rule"],
    }
    pipeline = InstructionPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    pipeline._multimodal_ready = True

    fact = _instruction_fact(
        action="APPROVE",
        authorization={"summary": "fresh approval", "allow_basis": ["new-rule"]},
    )
    await pipeline.process_instruction_fact(fact)

    payload = mock_neo4j.upsert_instruction_fact.call_args.kwargs["multimodal"].payload
    assert payload["authorization_summary"] == "fresh approval"
    assert payload["authorization_basis"] == ["new-rule"]


async def test_payment_security_event_pipeline(mock_neo4j, mock_ollama, mock_multimodal):
    pipeline = PaymentSecurityEventPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    event = {
        "event_id": "pevt-1",
        "message": "blocked",
        "resource": {"id": "pay-1", "instruction_id": "i1", "amount": 100, "currency": "USD"},
        "actor": {"user_id": "u1"},
        "event": {"action": "CREATE", "outcome": "DENY"},
        "payment_snapshot": {"created_by": {"user_id": "c1"}},
    }
    await pipeline.process(event)
    mock_neo4j.upsert_payment_security_event.assert_awaited_once()
    assert "multimodal" in mock_neo4j.upsert_payment_security_event.call_args.kwargs


async def test_payment_security_event_skips_missing_event_id(mock_neo4j, mock_ollama, mock_multimodal):
    pipeline = PaymentSecurityEventPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    await pipeline.process({})
    mock_neo4j.upsert_payment_security_event.assert_not_called()


async def test_payment_fact_pipeline(mock_neo4j, mock_ollama, mock_multimodal):
    pipeline = PaymentFactPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    fact = {
        "payment_id": "pay-1",
        "instruction_id": "i1",
        "status": "APPROVED",
        "amount": 250,
        "currency": "USD",
        "created_by": {"user_id": "c1"},
        "approved_by": {"user_id": "a1"},
    }
    await pipeline.process(fact)
    mock_neo4j.upsert_payment_fact.assert_awaited_once()
    payload = mock_neo4j.upsert_payment_fact.call_args.kwargs["multimodal"].payload
    assert payload["source"] == "payment_fact"


async def test_payment_fact_skips_missing_payment_id(mock_neo4j, mock_ollama, mock_multimodal):
    pipeline = PaymentFactPipeline(
        neo4j_writer=mock_neo4j,
        ollama_client=mock_ollama,
        multimodal_store=mock_multimodal,
    )
    await pipeline.process({})
    mock_neo4j.upsert_payment_fact.assert_not_called()
