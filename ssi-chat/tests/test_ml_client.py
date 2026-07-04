from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from chat_application.ml_client import PolicyPilotMlClient


@pytest.fixture
def mock_embedding() -> MagicMock:
    client = MagicMock()
    client.dimension = 768
    client.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    client.warmup = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_generation() -> MagicMock:
    client = MagicMock()
    client.generate_text = AsyncMock(return_value="Gemini answer.")
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_cypher() -> MagicMock:
    client = MagicMock()
    client.generate_cypher = AsyncMock(return_value="MATCH (n) RETURN n LIMIT 1")
    client.close = AsyncMock()
    return client


@pytest.fixture
def ml_client(mock_embedding, mock_generation, mock_cypher) -> PolicyPilotMlClient:
    return PolicyPilotMlClient(
        embedding_client=mock_embedding,
        generation_client=mock_generation,
        cypher_client=mock_cypher,
    )


async def test_embed_delegates_to_vertex_query(
    ml_client: PolicyPilotMlClient, mock_embedding: MagicMock
) -> None:
    vector = await ml_client.embed("find alerts")
    assert vector == [0.1, 0.2, 0.3]
    mock_embedding.embed_query.assert_awaited_once_with("find alerts")


async def test_warmup_delegates(ml_client: PolicyPilotMlClient, mock_embedding: MagicMock) -> None:
    await ml_client.warmup()
    mock_embedding.warmup.assert_awaited_once()


async def test_generate_cypher_delegates(
    ml_client: PolicyPilotMlClient, mock_cypher: MagicMock
) -> None:
    query = await ml_client.generate_cypher("how many?", "schema", mode="events")
    assert query == "MATCH (n) RETURN n LIMIT 1"
    mock_cypher.generate_cypher.assert_awaited_once_with(
        "how many?", "schema", mode="events"
    )


async def test_synthesize_answer_uses_gemini(
    ml_client: PolicyPilotMlClient, mock_generation: MagicMock
) -> None:
    answer = await ml_client.synthesize_answer(
        "How many alerts?",
        "context block",
        history=[{"role": "user", "content": "prior"}],
        mode="events",
    )
    assert answer == "Gemini answer."
    mock_generation.generate_text.assert_awaited_once()
    kwargs = mock_generation.generate_text.await_args.kwargs
    assert "How many alerts?" in kwargs["user"]
    assert "context block" in kwargs["user"]
    assert kwargs["history"] == [{"role": "user", "content": "prior"}]


async def test_summarize_authorization_why_returns_gemini_text(
    ml_client: PolicyPilotMlClient, mock_generation: MagicMock
) -> None:
    mock_generation.generate_text.return_value = "  Readable summary.  "
    result = await ml_client.summarize_authorization_why(
        approver="User A",
        authorization_summary="Raw OPA summary",
        authorization_basis=["role match"],
    )
    assert result == "Readable summary."
    user_prompt = mock_generation.generate_text.await_args.kwargs["user"]
    assert "role match" in user_prompt


async def test_summarize_authorization_why_falls_back_on_error(
    ml_client: PolicyPilotMlClient, mock_generation: MagicMock
) -> None:
    mock_generation.generate_text.side_effect = httpx.HTTPError("down")
    result = await ml_client.summarize_authorization_why(
        approver="User A",
        authorization_summary="Raw OPA summary",
    )
    assert result == "Raw OPA summary"


async def test_close_closes_all_clients(
    ml_client: PolicyPilotMlClient,
    mock_embedding: MagicMock,
    mock_generation: MagicMock,
    mock_cypher: MagicMock,
) -> None:
    await ml_client.close()
    mock_embedding.close.assert_awaited_once()
    mock_generation.close.assert_awaited_once()
    mock_cypher.close.assert_awaited_once()
