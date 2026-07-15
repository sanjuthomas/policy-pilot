"""Unit tests for DLQ classify, scheduler, store helpers, routes, integrity."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from etl.dlq.classify import classify_exception, is_retryable
from etl.dlq.models import DlqStatus, FailureClass, PipelineKind
from etl.dlq.pause import pause_registry
from etl.dlq.routes import build_dlq_router
from etl.dlq.scheduler import DlqScheduler
from etl.dlq.store import DlqStore
from etl.integrity import index_integrity_status
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j.exceptions import TransientError


def test_classify_transient_and_permanent():
    assert classify_exception(TransientError("x")) == FailureClass.TRANSIENT
    assert is_retryable(TransientError("x"))
    assert classify_exception(RuntimeError("boom")) == FailureClass.PERMANENT
    assert classify_exception(ValueError("invalid schema")) == FailureClass.POISON
    assert classify_exception(RuntimeError("rate limit 429")) == FailureClass.TRANSIENT


async def test_scheduler_replays_registered_handler():
    store = AsyncMock()
    doc = {
        "_id": "abc",
        "pipeline_kind": PipelineKind.PAYMENT_FACT.value,
        "payload": {"payment_id": "p1"},
        "event_id": "e1",
        "attempts": 1,
        "max_attempts": 5,
    }
    store.claim_next = AsyncMock(side_effect=[doc, None])
    store.mark_processed = AsyncMock()
    handler = AsyncMock()
    pause_registry.register_replay(PipelineKind.PAYMENT_FACT, handler)

    scheduler = DlqScheduler(store)
    count = await scheduler.drain_once(max_items=5)

    assert count == 1
    handler.assert_awaited_once_with({"payment_id": "p1"})
    store.mark_processed.assert_awaited_once_with("abc")


async def test_scheduler_marks_retry_on_failure():
    store = AsyncMock()
    doc = {
        "_id": "abc",
        "pipeline_kind": PipelineKind.PAYMENT_FACT.value,
        "payload": {"payment_id": "p1"},
        "attempts": 1,
        "max_attempts": 5,
    }
    store.claim_next = AsyncMock(side_effect=[doc, None])
    store.mark_retry_or_exhausted = AsyncMock(return_value="pending")
    handler = AsyncMock(side_effect=RuntimeError("neo4j down"))
    pause_registry.register_replay(PipelineKind.PAYMENT_FACT, handler)

    scheduler = DlqScheduler(store)
    await scheduler.drain_once(max_items=1)

    store.mark_retry_or_exhausted.assert_awaited_once()
    store.mark_processed.assert_not_called()


async def test_scheduler_missing_handler():
    store = AsyncMock()
    doc = {
        "_id": "abc",
        "pipeline_kind": PipelineKind.INSTRUCTION_FACT.value,
        "payload": {"instruction_id": "i1"},
        "attempts": 1,
        "max_attempts": 5,
    }
    store.claim_next = AsyncMock(side_effect=[doc, None])
    store.mark_retry_or_exhausted = AsyncMock(return_value="exhausted")
    pause_registry.register_replay(PipelineKind.INSTRUCTION_FACT, None)
    # Clear any previous handler by overwriting with None via private map
    pause_registry._handlers.pop(PipelineKind.INSTRUCTION_FACT, None)

    scheduler = DlqScheduler(store)
    await scheduler.drain_once(max_items=1)
    store.mark_retry_or_exhausted.assert_awaited_once()


async def test_pause_registry_snapshot():
    pause_registry.clear_paused("x")
    pause_registry.set_paused("x", reason="dlq_write_failed")
    snap = pause_registry.snapshot()
    assert snap["x"]["paused"] is True
    assert pause_registry.any_paused()
    pause_registry.clear_paused("x")
    assert not pause_registry.is_paused("x")


async def test_dlq_store_stats_when_disconnected():
    store = DlqStore()
    store._client = None
    store._col = None
    stats = await store.stats()
    assert stats["connected"] is False
    assert stats["depth"] == 0


async def test_dlq_store_insert_and_list(monkeypatch):
    store = DlqStore()
    col = AsyncMock()
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="oid1"))
    col.find_one = AsyncMock(return_value=None)
    col.create_index = AsyncMock()

    class FakeCursor:
        def sort(self, *_a, **_k):
            return self

        def skip(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        async def to_list(self, length=0):
            return [
                {
                    "_id": "oid1",
                    "status": "pending",
                    "payload": {"event_id": "e1"},
                }
            ]

    col.find = MagicMock(return_value=FakeCursor())
    store._col = col
    store._client = MagicMock()

    inserted = await store.insert_failure(
        pipeline_kind=PipelineKind.PAYMENT_FACT,
        consumer_name="payment_fact",
        topic="payments",
        partition=0,
        offset=3,
        consumer_group="g",
        payload={"payment_id": "p1", "event_id": "e1"},
        event_id="e1",
        entity_id="p1",
        failure_class=FailureClass.PERMANENT,
        error_message="boom",
        stage="process",
        realtime_attempts=2,
    )
    assert inserted == "oid1"
    rows = await store.list_entries(limit=10)
    assert rows[0]["id"] == "oid1"
    assert "payload" in rows[0] or rows[0]["payload_keys"] == ["event_id"]


async def test_dlq_store_mark_retry_exhausted():
    store = DlqStore()
    col = AsyncMock()
    col.update_one = AsyncMock()
    store._col = col
    status = await store.mark_retry_or_exhausted(
        {"_id": "x", "attempts": 8, "max_attempts": 8},
        error_message="still failing",
    )
    assert status == DlqStatus.EXHAUSTED.value


async def test_dlq_routes_reset_and_stats():
    store = AsyncMock()
    store.enabled = True
    store._col = MagicMock()
    store.stats = AsyncMock(
        return_value={"depth": 2, "by_status": {"pending": 2}, "connected": True, "enabled": True}
    )
    store.list_entries = AsyncMock(return_value=[{"id": "1", "status": "pending", "payload": {}}])
    store.get_entry = AsyncMock(return_value={"id": "1", "payload": {"a": 1}})
    store.reset_entries = AsyncMock(return_value=2)
    scheduler = AsyncMock()
    scheduler.drain_once = AsyncMock(return_value=1)

    app = FastAPI()
    app.include_router(build_dlq_router(store, scheduler), prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/dlq/stats").status_code == 200
        assert client.get("/api/dlq/entries").json()["count"] == 1
        assert client.get("/api/dlq/entries/1").status_code == 200
        reset = client.post("/api/dlq/reset", json={"reason": "test"})
        assert reset.status_code == 200
        assert reset.json()["reset"] == 2
        resumed = client.post("/api/dlq/resume-consumers", json={})
        assert resumed.status_code == 200


async def test_index_integrity_banner_on_lag():
    async def lag():
        return 11

    consumer = MagicMock()
    consumer.estimated_lag = lag
    dlq = AsyncMock()
    dlq.stats = AsyncMock(
        return_value={
            "depth": 0,
            "by_status": {},
            "oldest_pending_age_seconds": None,
            "connected": True,
            "enabled": True,
        }
    )
    pause_registry.clear_paused("instruction_security_event")
    status = await index_integrity_status(
        dlq=dlq,
        instruction_security_event_consumer=consumer,
        instruction_consumer=consumer,
        payment_security_event_consumer=consumer,
        payment_fact_consumer=consumer,
    )
    assert status["show_banner"] is True
    assert status["kafka_lag_total"] == 44
    assert "behind" in (status["banner_message"] or "").lower()
