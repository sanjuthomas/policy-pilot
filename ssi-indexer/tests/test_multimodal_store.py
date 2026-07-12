from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from etl.multimodal_store import (
    MultimodalNeo4jStore,
    _chunk_record_id,
    _denormalized_fields,
    _estimate_tokens,
    _node_to_result,
    _numeric_summary,
    _payload_from_node,
    _source_filter_values,
    event_document_id,
    instruction_document_id,
    payment_document_id,
)


class _AsyncRecords:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._records:
            raise StopAsyncIteration
        return self._records.pop(0)


@pytest.fixture
def neo4j_session() -> AsyncMock:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    tx = AsyncMock()
    tx.run = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


@pytest.fixture
def store(neo4j_session: AsyncMock) -> MultimodalNeo4jStore:
    writer = MagicMock()
    writer._driver = MagicMock()
    writer._driver.session = MagicMock(return_value=neo4j_session)
    return MultimodalNeo4jStore(writer)


def test_document_id_helpers_are_stable() -> None:
    assert event_document_id("se-1") == event_document_id("se-1")
    assert instruction_document_id("instr-1") == instruction_document_id("instr-1")
    assert payment_document_id("pay-1") == payment_document_id("pay-1")


def test_estimate_tokens_and_numeric_summary() -> None:
    assert _estimate_tokens("") == 0
    assert _estimate_tokens("one two three") >= 1
    assert _numeric_summary([]) == {"min": 0, "max": 0, "avg": 0, "median": 0}
    assert _numeric_summary([2, 4])["median"] == 3


def test_payload_helpers() -> None:
    assert _chunk_record_id({"event_id": "e1"}) == "e1"
    assert _payload_from_node({}) == {}
    assert _payload_from_node({"payload_json": '{"event_id": "e1"}'})["event_id"] == "e1"
    fields = _denormalized_fields(
        {
            "event_id": "e1",
            "merged": {"action": "READ", "outcome": "ALLOW"},
        }
    )
    assert fields["action"] == "READ"
    node = {
        "search_text": "wire transfer",
        "payload_json": json.dumps({"event_id": "e1", "search_text": "wire transfer"}),
    }
    result = _node_to_result(node, 0.9)
    assert result["event_id"] == "e1"
    assert result["score"] == 0.9


def test_source_filter_values() -> None:
    assert _source_filter_values(None) is None
    assert _source_filter_values("security_events") == [
        "instruction_security_event",
        "payment_security_event",
    ]
    assert _source_filter_values("payment") == ["payment_fact"]
    assert _source_filter_values("instruction_state") == ["instruction_state"]


async def test_document_count(store: MultimodalNeo4jStore, neo4j_session: AsyncMock) -> None:
    result = AsyncMock()
    result.single = AsyncMock(return_value={"count": 12})
    neo4j_session.run = AsyncMock(return_value=result)

    assert await store.document_count() == 12
    assert await store.has_documents() is True


async def test_ensure_indexes_runs_once(store: MultimodalNeo4jStore, neo4j_session: AsyncMock) -> None:
    neo4j_session.run = AsyncMock()
    await store.ensure_indexes(1024)
    await store.ensure_indexes(1024)
    neo4j_session.run.assert_awaited_once()


async def test_upsert_instruction_state(store: MultimodalNeo4jStore, neo4j_session: AsyncMock) -> None:
    tx = await neo4j_session.begin_transaction()
    await store.upsert_instruction_state(
        "instr-1",
        "pending wire",
        {"status": "PENDING"},
        dense_vector=[0.1, 0.2],
    )
    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["instruction_id"] == "instr-1"
    assert call_kwargs["source"] == "instruction_state"
    tx.commit.assert_awaited_once()


async def test_get_instruction_state_payload_missing(
    store: MultimodalNeo4jStore, neo4j_session: AsyncMock
) -> None:
    result = AsyncMock()
    result.single = AsyncMock(return_value=None)
    neo4j_session.run = AsyncMock(return_value=result)
    assert await store.get_instruction_state_payload("missing") is None


async def test_get_instruction_state_payload_found(
    store: MultimodalNeo4jStore, neo4j_session: AsyncMock
) -> None:
    result = AsyncMock()
    result.single = AsyncMock(
        return_value={"d": {"payload_json": json.dumps({"authorization_summary": "ok"})}}
    )
    neo4j_session.run = AsyncMock(return_value=result)
    payload = await store.get_instruction_state_payload("instr-1")
    assert payload["authorization_summary"] == "ok"


async def test_patch_instruction_state_authorization_no_summary(
    store: MultimodalNeo4jStore, neo4j_session: AsyncMock
) -> None:
    neo4j_session.run = AsyncMock()
    await store.patch_instruction_state_authorization(
        "instr-1",
        approved_at="2024-01-01",
        authorization_summary=None,
        authorization_basis=[],
    )
    neo4j_session.run.assert_not_awaited()


async def test_patch_instruction_state_authorization_updates(
    store: MultimodalNeo4jStore, neo4j_session: AsyncMock
) -> None:
    lookup = AsyncMock()
    lookup.single = AsyncMock(
        return_value={
            "d": {
                "search_text": "wire",
                "embedding": [0.5, 0.5],
                "payload_json": json.dumps({"instruction_id": "instr-1"}),
            }
        }
    )
    neo4j_session.run = AsyncMock(return_value=lookup)
    tx = await neo4j_session.begin_transaction()

    await store.patch_instruction_state_authorization(
        "instr-1",
        approved_at="2024-06-01",
        authorization_summary="approved by manager",
        authorization_basis=["role-match"],
    )
    neo4j_session.run.assert_awaited_once()
    tx.run.assert_awaited_once()
    tx.commit.assert_awaited_once()


async def test_search_dense_returns_hits(store: MultimodalNeo4jStore, neo4j_session: AsyncMock) -> None:
    node = {
        "search_text": "denied payment",
        "payload_json": json.dumps({"event_id": "evt-1"}),
    }
    neo4j_session.run = AsyncMock(return_value=_AsyncRecords([{"node": node, "score": 0.88}]))
    hits = await store.search_dense([0.1, 0.2], limit=5)
    assert hits[0]["event_id"] == "evt-1"
    assert hits[0]["score"] == 0.88


async def test_search_text_chunk_stats(store: MultimodalNeo4jStore, neo4j_session: AsyncMock) -> None:
    neo4j_session.run = AsyncMock(
        return_value=_AsyncRecords(
            [
                {
                    "document_id": "doc-1",
                    "source": "instruction_security_event",
                    "event_id": "evt-1",
                    "instruction_id": None,
                    "payment_id": None,
                    "search_text": "short text",
                }
            ]
        )
    )
    stats = await store.search_text_chunk_stats(top_n=1)
    assert stats["points_count"] == 1
    assert stats["store"] == "neo4j_multimodal"
    assert stats["top_chunks"][0]["rank"] == 1
