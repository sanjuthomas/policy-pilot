from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_ollama():
    client = MagicMock()
    client.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    client.chat = AsyncMock(return_value="mocked answer")
    client.generate_cypher = AsyncMock(
        return_value="MATCH (e:SecurityEvent) RETURN e LIMIT 1"
    )
    client.synthesize_answer = AsyncMock(return_value="Synthesized answer.")
    client.summarize_authorization_why = AsyncMock(return_value="Policy allowed approval.")
    return client


@pytest.fixture
def mock_qdrant():
    client = MagicMock()
    client.connect = MagicMock()
    client.close = MagicMock()
    client.has_collection = MagicMock(return_value=False)
    client.search_vector = MagicMock(return_value=[])
    client.search_bm25 = MagicMock(return_value=[])
    client.fetch_by_event_id = MagicMock(return_value=None)
    client.fetch_by_instruction_id = MagicMock(return_value=None)
    client.fetch_instruction_approve_events = MagicMock(return_value=[])
    return client


@pytest.fixture
def mock_neo4j():
    client = MagicMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.run_cypher = AsyncMock(return_value=[])
    client.lookup_instruction_for_event = AsyncMock(return_value=[])
    return client


@pytest.fixture
def test_client(mock_ollama, mock_qdrant, mock_neo4j):
    import chat_application.main as main_module

    main_module.ollama_client = mock_ollama
    main_module.qdrant_client = mock_qdrant
    main_module.neo4j_client = mock_neo4j
    main_module.rag_service = None

    with TestClient(main_module.app) as client:
        yield client
