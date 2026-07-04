from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from vertex_client.embeddings import VertexEmbeddingClient


@pytest.fixture
def client() -> VertexEmbeddingClient:
    return VertexEmbeddingClient(
        project_id="test-project",
        region="us-central1",
        model="text-embedding-004",
        dimension=3,
    )


async def test_embed_empty_text_raises(client: VertexEmbeddingClient) -> None:
    with pytest.raises(ValueError, match="empty text"):
        await client.embed("   ")


async def test_embed_returns_vector(client: VertexEmbeddingClient) -> None:
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=[0.1, 0.2, 0.3])]

    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value.models.embed_content.return_value = mock_response
        vector = await client.embed("instruction_id: abc")

    assert vector == [0.1, 0.2, 0.3]
    assert client.dimension == 3


async def test_embed_query_uses_query_task(client: VertexEmbeddingClient) -> None:
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=[1.0, 2.0, 3.0])]

    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value.models.embed_content.return_value = mock_response
        await client.embed_query("find FX payments")

    _, kwargs = mock_get_client.return_value.models.embed_content.call_args
    assert kwargs["config"].task_type == "RETRIEVAL_QUERY"


async def test_embed_dimension_mismatch_raises(client: VertexEmbeddingClient) -> None:
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=[0.1, 0.2])]

    with patch.object(client, "_get_client") as mock_get_client:
        mock_get_client.return_value.models.embed_content.return_value = mock_response
        with pytest.raises(RuntimeError, match="dimension mismatch"):
            await client.embed("bad dimension")


async def test_warmup(client: VertexEmbeddingClient) -> None:
    with patch.object(client, "embed", return_value=[0.5, 0.5, 0.5]) as mock_embed:
        await client.warmup()
    mock_embed.assert_awaited_once_with("warmup")


async def test_dimension_before_embed_raises() -> None:
    unset = VertexEmbeddingClient(
        project_id="test-project",
        region="us-central1",
        model="text-embedding-004",
    )
    with pytest.raises(RuntimeError, match="not initialized"):
        _ = unset.dimension
