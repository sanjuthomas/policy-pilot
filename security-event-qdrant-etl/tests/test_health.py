"""Tests for etl.health component checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from etl.config import settings
from etl.health import (
    _qdrant_vector_names,
    _status,
    check_kafka,
    check_neo4j,
    check_ollama,
    check_qdrant_bm25,
    check_qdrant_vector,
    component_status,
)


def test_status_helper():
    result = _status(True, "up", detail="ok", count=5)
    assert result == {"ok": True, "status": "up", "detail": "ok", "count": 5}


def test_qdrant_vector_names_dict():
    params = MagicMock()
    params.vectors = {"dense": MagicMock(), "other": MagicMock()}
    params.sparse_vectors = {"bm25": MagicMock()}
    info = MagicMock()
    info.config.params = params

    dense, sparse = _qdrant_vector_names(info)
    assert dense == {"dense", "other"}
    assert sparse == {"bm25"}


def test_qdrant_vector_names_no_params():
    info = MagicMock()
    info.config.params = None
    assert _qdrant_vector_names(info) == (set(), set())


def test_qdrant_vector_names_non_dict_vectors():
    params = MagicMock()
    params.vectors = MagicMock()
    params.sparse_vectors = None
    info = MagicMock()
    info.config.params = params

    dense, sparse = _qdrant_vector_names(info)
    assert dense == {settings.qdrant_dense_vector_name}
    assert sparse == set()


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


def test_check_qdrant_vector_not_connected():
    store = MagicMock()
    store._client = None
    result = check_qdrant_vector(store)
    assert result["ok"] is False


def test_check_qdrant_vector_empty_collection():
    store = MagicMock()
    store._client = MagicMock()
    store.has_collection.return_value = False
    result = check_qdrant_vector(store)
    assert result["ok"] is False
    assert result["status"] == "empty"


def test_check_qdrant_vector_missing_dense():
    store = MagicMock()
    store._client = MagicMock()
    store.has_collection.return_value = True
    info = MagicMock()
    info.points_count = 10
    info.config.params = MagicMock(vectors={"other": MagicMock()}, sparse_vectors={})
    store._client.get_collection.return_value = info

    result = check_qdrant_vector(store)
    assert result["ok"] is False
    assert "dense vector" in result["detail"]


def test_check_qdrant_vector_up():
    store = MagicMock()
    store._client = MagicMock()
    store.has_collection.return_value = True
    info = MagicMock()
    info.points_count = 42
    info.config.params = MagicMock(
        vectors={settings.qdrant_dense_vector_name: MagicMock()},
        sparse_vectors={},
    )
    store._client.get_collection.return_value = info

    result = check_qdrant_vector(store)
    assert result["ok"] is True
    assert result["points_count"] == 42


def test_check_qdrant_bm25_missing_sparse():
    store = MagicMock()
    store._client = MagicMock()
    store.has_collection.return_value = True
    info = MagicMock()
    info.points_count = 5
    info.config.params = MagicMock(vectors={}, sparse_vectors={})
    store._client.get_collection.return_value = info

    result = check_qdrant_bm25(store)
    assert result["ok"] is False
    assert "BM25 vector" in result["detail"]


def test_check_qdrant_bm25_up():
    store = MagicMock()
    store._client = MagicMock()
    store.has_collection.return_value = True
    info = MagicMock()
    info.points_count = 7
    info.config.params = MagicMock(
        vectors={},
        sparse_vectors={settings.qdrant_bm25_vector_name: MagicMock()},
    )
    store._client.get_collection.return_value = info

    result = check_qdrant_bm25(store)
    assert result["ok"] is True


async def test_check_ollama_model_missing():
    client = MagicMock()
    client._dimension = None

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "other-model:latest"}]}

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)

    with patch("etl.health.httpx.AsyncClient", return_value=mock_http):
        result = await check_ollama(client)

    assert result["ok"] is False
    assert "not found" in result["detail"]


async def test_check_ollama_up():
    client = MagicMock()
    client._dimension = 1024

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "models": [{"name": settings.ollama_embedding_model}, {"name": "llama3"}]
    }

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)

    with patch("etl.health.httpx.AsyncClient", return_value=mock_http):
        result = await check_ollama(client)

    assert result["ok"] is True
    assert result["dimension"] == 1024
    assert result["embeddings"] == "ready"


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
    ollama = MagicMock()

    with (
        patch("etl.health.check_kafka", AsyncMock(return_value={"ok": True, "status": "up"})),
        patch("etl.health.check_neo4j", AsyncMock(return_value={"ok": True, "status": "up"})),
        patch("etl.health.check_ollama", AsyncMock(return_value={"ok": False, "status": "down"})),
        patch("etl.health.check_qdrant_vector", return_value={"ok": True, "status": "up"}),
        patch("etl.health.check_qdrant_bm25", return_value={"ok": True, "status": "up"}),
    ):
        result = await component_status(
            instruction_security_event_consumer=consumer,
            qdrant_store=store,
            neo4j_writer=writer,
            ollama_client=ollama,
        )

    assert set(result.keys()) == {"kafka", "ollama", "qdrant_vector", "qdrant_bm25", "neo4j"}
    assert result["ollama"]["ok"] is False
