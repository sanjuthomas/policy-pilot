from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from chat_application.gemini.client import PolicyPilotMlClient
from cypher_builder import GraphIntent


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
def ml_client(mock_embedding, mock_generation) -> PolicyPilotMlClient:
    return PolicyPilotMlClient(
        embedding_client=mock_embedding,
        generation_client=mock_generation,
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


async def test_extract_graph_query_plan_parses_vertex_json(
    ml_client: PolicyPilotMlClient, mock_generation: MagicMock
) -> None:
    mock_generation.generate_text.return_value = (
        '{"intent":"security_event_aggregate","operation":"count",'
        '"time_window":"today","domain":"payments","severity":"ALERT","denial":true}'
    )
    plan = await ml_client.extract_graph_query_plan("How many payment alerts today?", mode="events")
    assert plan.intent == GraphIntent.SECURITY_EVENT_AGGREGATE
    assert plan.time_window == "today"
    mock_generation.generate_text.assert_awaited_once()


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


async def test_summarize_authorization_why_falls_back_on_error(
    ml_client: PolicyPilotMlClient, mock_generation: MagicMock
) -> None:
    mock_generation.generate_text.side_effect = httpx.HTTPError("down")
    result = await ml_client.summarize_authorization_why(
        approver="User A",
        authorization_summary="Raw OPA summary",
    )
    assert result == "Raw OPA summary"


async def test_close_closes_vertex_clients(
    ml_client: PolicyPilotMlClient,
    mock_embedding: MagicMock,
    mock_generation: MagicMock,
) -> None:
    await ml_client.close()
    mock_embedding.close.assert_awaited_once()
    mock_generation.close.assert_awaited_once()
