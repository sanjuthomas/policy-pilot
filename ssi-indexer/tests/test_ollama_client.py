"""Tests for etl.ollama_client chat/Cypher helpers with mocked httpx."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from etl.ollama_client import OllamaChatClient


@pytest.fixture
def client() -> OllamaChatClient:
    return OllamaChatClient()


async def test_chat_returns_content(client: OllamaChatClient) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"message": {"content": "MATCH (n) RETURN n LIMIT 1"}}

    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.post = AsyncMock(return_value=mock_response)

    with patch.object(client, "_client", AsyncMock(return_value=mock_http)):
        content = await client.chat(system="sys", user="user")

    assert content == "MATCH (n) RETURN n LIMIT 1"


async def test_close(client: OllamaChatClient) -> None:
    mock_http = AsyncMock()
    mock_http.is_closed = False
    client._http = mock_http
    await client.close()
    mock_http.aclose.assert_awaited_once()
    assert client._http is None


async def test_client_recreates_when_closed(client: OllamaChatClient) -> None:
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


async def test_chat_http_error(client: OllamaChatClient) -> None:
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
            await client.chat(system="sys", user="user")
