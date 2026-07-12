"""Tests for etl.health component checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from etl.config import settings
from etl.health import (
    _status,
    check_kafka,
    check_multimodal_vector,
    check_neo4j,
    check_vertex_embeddings,
    component_status,
)


def test_status_helper():
    result = _status(True, "up", detail="ok", count=5)
    assert result == {"ok": True, "status": "up", "detail": "ok", "count": 5}


async def test_check_kafka_disabled():
    consumer = MagicMock()
    with patch.object(settings, "kafka_enabled", False):
        result = await check_kafka(consumer)
    assert result["ok"] is True
    assert result["status"] == "disabled"


async def test_check_kafka_not_started():
    consumer = MagicMock()
    consumer._consumer = None
    consumer._task = None
    with patch.object(settings, "kafka_enabled", True):
        result = await check_kafka(consumer)
    assert result["ok"] is False
    assert result["status"] == "down"


async def test_check_kafka_task_done_with_exception():
    consumer = MagicMock()
    consumer._consumer = MagicMock()
    consumer._task = MagicMock()
    consumer._task.done.return_value = True
    consumer._task.exception.return_value = RuntimeError("boom")

    with patch.object(settings, "kafka_enabled", True):
        result = await check_kafka(consumer)
    assert result["ok"] is False
    assert "boom" in result["detail"]


async def test_check_kafka_running():
    consumer = MagicMock()
    consumer._consumer = MagicMock()
    consumer._consumer._client.cluster.brokers.return_value = {"b1": {}, "b2": {}}
    consumer._task = MagicMock()
    consumer._task.done.return_value = False

    with patch.object(settings, "kafka_enabled", True):
        result = await check_kafka(consumer)
    assert result["ok"] is True
    assert result["status"] == "up"
    assert result["brokers"] == 2


async def test_check_multimodal_vector_missing_index():
    store = MagicMock()
    store._writer = MagicMock()
    store._writer._driver = MagicMock()
    store.document_count = AsyncMock(return_value=0)

    with patch("etl.health._index_exists", AsyncMock(return_value=False)):
        result = await check_multimodal_vector(store)

    assert result["ok"] is False
    assert result["status"] == "empty"
    assert "vector index" in result["detail"]


async def test_check_multimodal_vector_up():
    store = MagicMock()
    store._writer = MagicMock()
    store.document_count = AsyncMock(return_value=42)

    with patch("etl.health._index_exists", AsyncMock(return_value=True)):
        result = await check_multimodal_vector(store)

    assert result["ok"] is True
    assert result["documents_count"] == 42


async def test_check_vertex_embeddings_not_ready():
    client = MagicMock()
    client._ready = False
    client._dimension = 768
    result = await check_vertex_embeddings(client)
    assert result["ok"] is False
    assert "not warmed up" in result["detail"]


async def test_check_vertex_embeddings_up():
    client = MagicMock()
    client._ready = True
    client._dimension = 768
    result = await check_vertex_embeddings(client)
    assert result["ok"] is True
    assert result["embeddings"] == "ready"
    assert result["dimension"] == 768


async def test_check_neo4j_not_connected():
    writer = MagicMock()
    writer._driver = None
    result = await check_neo4j(writer)
    assert result["ok"] is False


async def test_check_neo4j_up():
    writer = MagicMock()
    writer._driver = AsyncMock()
    writer._driver.verify_connectivity = AsyncMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    result_mock = AsyncMock()
    result_mock.single = AsyncMock()
    session.run = AsyncMock(return_value=result_mock)
    writer._driver.session = MagicMock(return_value=session)
    writer.graph_stats = AsyncMock(return_value={"SecurityEvent": 3, "User": 2})

    result = await check_neo4j(writer)
    assert result["ok"] is True
    assert result["total_nodes"] == 5


async def test_component_status_aggregates():
    consumer = MagicMock()
    store = MagicMock()
    writer = MagicMock()
    embedding = MagicMock()

    with (
        patch("etl.health.check_kafka", AsyncMock(return_value={"ok": True, "status": "up"})),
        patch("etl.health.check_neo4j", AsyncMock(return_value={"ok": True, "status": "up"})),
        patch(
            "etl.health.check_vertex_embeddings",
            AsyncMock(return_value={"ok": False, "status": "down"}),
        ),
        patch(
            "etl.health.check_multimodal_vector",
            AsyncMock(return_value={"ok": True, "status": "up"}),
        ),
    ):
        result = await component_status(
            instruction_security_event_consumer=consumer,
            multimodal_store=store,
            neo4j_writer=writer,
            embedding_client=embedding,
        )

    assert set(result.keys()) == {
        "kafka",
        "vertex_embeddings",
        "multimodal_vector",
        "neo4j",
    }
    assert result["vertex_embeddings"]["ok"] is False
