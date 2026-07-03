"""Tests for etl.ollama_client with mocked httpx."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from etl.ollama_client import OllamaEmbeddingClient


@pytest.fixture
def client() -> OllamaEmbeddingClient:
    return OllamaEmbeddingClient()


async def test_embed_empty_text_raises(client: OllamaEmbeddingClient):
    with pytest.raises(ValueError, match="empty text"):
        await client.embed("   ")


async def test_embed_embeddings_list_format(client: OllamaEmbeddingClient):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch.object(client, "_client", AsyncMock(return_value=mock_http)):
        vector = await client.embed("hello world")

    assert vector == [0.1, 0.2, 0.3]
    assert client.dimension == 3
    mock_http.post.assert_awaited_once()


async def test_embed_single_embedding_format(client: OllamaEmbeddingClient):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"embedding": [1.0, 2.0]}

    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch.object(client, "_client", AsyncMock(return_value=mock_http)):
        vector = await client.embed("test")

    assert vector == [1.0, 2.0]


async def test_embed_unexpected_response_raises(client: OllamaEmbeddingClient):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"unexpected": True}

    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch.object(client, "_client", AsyncMock(return_value=mock_http)):
        with pytest.raises(RuntimeError, match="unexpected Ollama embed response"):
            await client.embed("bad response")


async def test_warmup(client: OllamaEmbeddingClient):
    async def fake_embed(text: str) -> list[float]:
        client._dimension = 2
        return [0.5, 0.5]

    with patch.object(client, "embed", side_effect=fake_embed) as mock_embed:
        await client.warmup()
    mock_embed.assert_awaited_once_with("warmup")
    assert client.dimension == 2


async def test_dimension_before_embed_raises(client: OllamaEmbeddingClient):
    with pytest.raises(RuntimeError, match="not initialized"):
        _ = client.dimension


async def test_close(client: OllamaEmbeddingClient):
    mock_http = AsyncMock()
    mock_http.is_closed = False
    client._http = mock_http
    await client.close()
    mock_http.aclose.assert_awaited_once()
    assert client._http is None


async def test_client_recreates_when_closed(client: OllamaEmbeddingClient):
    closed_http = AsyncMock()
    closed_http.is_closed = True
    client._http = closed_http

    with patch("etl.ollama_client.httpx.AsyncClient") as mock_cls:
        new_http = AsyncMock()
        new_http.is_closed = False
        mock_cls.return_value = new_http
        result = await client._client()

    assert result is new_http
    mock_cls.assert_called_once()


async def test_embed_http_error(client: OllamaEmbeddingClient):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error",
        request=MagicMock(),
        response=MagicMock(),
    )

    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch.object(client, "_client", AsyncMock(return_value=mock_http)):
        with pytest.raises(httpx.HTTPStatusError):
            await client.embed("fail")
