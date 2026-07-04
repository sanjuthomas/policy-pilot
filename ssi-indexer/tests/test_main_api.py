"""Tests for FastAPI endpoints in etl.main."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from etl.admin import get_admin_subject
from etl.models import Subject
from fastapi.testclient import TestClient


def _async_mocks(*consumers):
    for consumer in consumers:
        consumer.start = AsyncMock()
        consumer.close = AsyncMock()


@pytest.fixture
def client():
    with patch("etl.main.instruction_security_event_consumer") as mock_consumer, patch(
        "etl.main.neo4j_writer"
    ) as mock_neo4j, patch("etl.main.embedding_client") as mock_embedding, patch(
        "etl.main.generation_client"
    ) as mock_generation, patch(
        "etl.main.multimodal_store"
    ) as mock_multimodal, patch(
        "etl.main.instruction_consumer"
    ) as mock_instruction_consumer, patch(
        "etl.main.payment_security_event_consumer"
    ) as mock_payment_event_consumer, patch(
        "etl.main.payment_fact_consumer"
    ) as mock_payment_fact_consumer:
        mock_consumer._consumer = MagicMock()
        mock_consumer._task = MagicMock()
        mock_consumer._task.done.return_value = False

        mock_neo4j.connect = AsyncMock()
        mock_neo4j.close = AsyncMock()
        mock_embedding.warmup = AsyncMock()
        mock_embedding.close = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1, 0.2])
        mock_generation.close = AsyncMock()
        mock_generation.generate_text = AsyncMock(
            return_value='{"intent":"security_event_aggregate","operation":"count","severity":"ALERT","denial":true,"time_window":"today","confidence":0.95}'
        )
        mock_multimodal.ensure_indexes = AsyncMock()

        _async_mocks(
            mock_consumer,
            mock_instruction_consumer,
            mock_payment_event_consumer,
            mock_payment_fact_consumer,
        )

        from etl.main import app

        @asynccontextmanager
        async def noop_lifespan(_: object):
            yield

        app.router.lifespan_context = noop_lifespan
        admin_subject = Subject(
            user_id="admin-001",
            title="Platform Admin",
            roles=["PLATFORM_ADMIN"],
        )
        app.dependency_overrides[get_admin_subject] = lambda: admin_subject

        with TestClient(app) as test_client:
            yield test_client, mock_neo4j, mock_embedding, mock_multimodal

        app.dependency_overrides.clear()


def test_index(client):
    test_client, _, _, _ = client
    response = test_client.get("/")
    assert response.status_code == 200


def test_health_endpoint(client):
    test_client, _, _, _ = client
    with patch(
        "etl.main.component_status",
        AsyncMock(
            return_value={
                "kafka": {"ok": True, "status": "up"},
                "vertex_embeddings": {"ok": True, "status": "up"},
                "multimodal_vector": {"ok": True, "status": "up"},
                "multimodal_fulltext": {"ok": True, "status": "up"},
                "neo4j": {"ok": True, "status": "up"},
            }
        ),
    ):
        response = test_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UP"


def test_stats_endpoint(client):
    test_client, _, _, _ = client
    status = {
        "kafka": {"ok": False, "status": "down"},
        "vertex_embeddings": {"ok": True, "status": "up"},
        "multimodal_vector": {"ok": True, "status": "up"},
        "multimodal_fulltext": {"ok": True, "status": "up"},
        "neo4j": {"ok": True, "status": "up"},
    }
    with patch("etl.main.component_status", AsyncMock(return_value=status)):
        stats = test_client.get("/api/stats").json()
    assert stats["all_ok"] is False
    assert stats["components"]["kafka"]["ok"] is False


def test_search_profiles_list(client):
    test_client, _, _, _ = client
    response = test_client.get("/api/search-profiles")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    assert all(profile["wired"] for profile in body["profiles"])


def test_search_profile_detail(client):
    test_client, _, _, _ = client
    response = test_client.get("/api/search-profiles/payment_fact")
    assert response.status_code == 200
    body = response.json()
    assert body["entity"] == "payment_fact"
    assert body["wired"] is True
    assert any(item.get("path") == "payment_id" for item in body["includes"])


def test_search_profile_detail_not_found(client):
    test_client, _, _, _ = client
    response = test_client.get("/api/search-profiles/not-an-entity")
    assert response.status_code == 404


def test_vector_chunk_stats(client):
    test_client, _, _, mock_multimodal = client
    mock_multimodal.search_text_chunk_stats = AsyncMock(
        return_value={
            "collection": "neo4j_multimodal",
            "indexing_model": "one_point_per_record",
            "points_count": 2,
            "search_text_field": "search_text",
            "summary": {
                "char_count": {"min": 10, "max": 100, "avg": 55, "median": 55},
                "word_count": {"min": 2, "max": 20, "avg": 11, "median": 11},
                "estimated_tokens": {"min": 3, "max": 26, "avg": 14, "median": 14},
            },
            "by_source": {"instruction_security_event": {"count": 2, "max_chars": 100, "avg_chars": 55}},
            "top_chunks": [{"rank": 1, "char_count": 100, "source": "instruction_security_event"}],
        }
    )

    response = test_client.get("/api/vector/chunk-stats?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["points_count"] == 2
    assert body["indexing_model"] == "one_point_per_record"
    assert body["indexing_notes"]["chunking"].startswith("none")
    assert body["embedding_context_tokens"] == 32768
    assert len(body["search_profiles"]) == 4
    assert len(body["top_chunks"]) == 1


def test_vector_chunk_stats_error(client):
    test_client, _, _, mock_multimodal = client
    mock_multimodal.search_text_chunk_stats = AsyncMock(side_effect=RuntimeError("neo4j down"))
    response = test_client.get("/api/vector/chunk-stats")
    assert response.status_code == 503


def test_search_vector(client):
    test_client, _, mock_embedding, mock_multimodal = client
    mock_embedding.embed_query = AsyncMock(return_value=[0.1, 0.2])
    mock_multimodal.search_dense = AsyncMock(return_value=[{"score": 0.9, "event_id": "e1"}])

    response = test_client.post("/api/search/vector", json={"query": "wire transfer"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "vector"
    assert body["count"] == 1


def test_search_vector_error(client):
    test_client, _, mock_embedding, _ = client
    mock_embedding.embed_query = AsyncMock(side_effect=RuntimeError("vertex down"))
    response = test_client.post("/api/search/vector", json={"query": "fail"})
    assert response.status_code == 503


def test_search_bm25(client):
    test_client, _, _, mock_multimodal = client
    mock_multimodal.search_bm25 = AsyncMock(return_value=[])

    response = test_client.post("/api/search/bm25", json={"query": "denied"})
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_search_hybrid(client):
    test_client, _, mock_embedding, mock_multimodal = client
    mock_embedding.embed_query = AsyncMock(return_value=[0.3])
    mock_multimodal.search_hybrid = AsyncMock(return_value=[{"score": 0.8}])

    response = test_client.post("/api/search/hybrid", json={"query": "hybrid"})
    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"


def test_graph_search_events(client):
    test_client, mock_neo4j, _, _ = client
    mock_neo4j.search_events = AsyncMock(return_value=[{"event_id": "e1"}])

    response = test_client.get("/api/graph/events?q=deny")
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_graph_event_detail_not_found(client):
    test_client, mock_neo4j, _, _ = client
    mock_neo4j.get_event_subgraph = AsyncMock(return_value=None)

    response = test_client.get("/api/graph/events/missing")
    assert response.status_code == 404


def test_graph_instruction_detail(client):
    test_client, mock_neo4j, _, _ = client
    mock_neo4j.get_instruction_subgraph = AsyncMock(return_value={"instruction_id": "i1"})

    response = test_client.get("/api/graph/instructions/i1")
    assert response.status_code == 200


def test_graph_instruction_detail_not_found(client):
    test_client, mock_neo4j, _, _ = client
    mock_neo4j.get_instruction_subgraph = AsyncMock(return_value=None)
    response = test_client.get("/api/graph/instructions/missing")
    assert response.status_code == 404


def test_cypher_run_valid(client):
    test_client, mock_neo4j, _, _ = client
    mock_neo4j.run_read_cypher = AsyncMock(return_value=[{"n": 1}])

    response = test_client.post(
        "/api/cypher/run",
        json={"cypher": "MATCH (n) RETURN count(n) AS n LIMIT 1"},
    )
    assert response.status_code == 200
    assert response.json()["row_count"] == 1


def test_cypher_run_invalid(client):
    test_client, _, _, _ = client
    response = test_client.post(
        "/api/cypher/run",
        json={"cypher": "CREATE (n) RETURN n LIMIT 1"},
    )
    assert response.status_code == 400


def test_cypher_run_neo4j_error(client):
    test_client, mock_neo4j, _, _ = client
    mock_neo4j.run_read_cypher = AsyncMock(side_effect=RuntimeError("neo4j error"))
    response = test_client.post(
        "/api/cypher/run",
        json={"cypher": "MATCH (n) RETURN n LIMIT 1"},
    )
    assert response.status_code == 502


def test_intent_extract_success(client):
    test_client, _, _, _ = client

    response = test_client.post(
        "/api/intent/extract",
        json={"question": "How many payment ALERT events happened today?", "mode": "events"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "vertex_gemini"
    assert body["plan"]["intent"] == "security_event_aggregate"
    assert body["plan"]["severity"] == "ALERT"


def test_intent_extract_auth_required(client):
    test_client, _, _, _ = client
    from etl.main import app

    app.dependency_overrides.clear()
    response = test_client.post(
        "/api/intent/extract",
        json={"question": "How many alerts today?", "mode": "events"},
    )
    assert response.status_code == 401
