from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from chat_application.ollama import OllamaClient, _extract_cypher


class TestExtractCypher:
    def test_strips_markdown_fence(self) -> None:
        raw = """```cypher
MATCH (n) RETURN n LIMIT 1
```"""
        assert _extract_cypher(raw) == "MATCH (n) RETURN n LIMIT 1"

    def test_removes_comment_lines(self) -> None:
        raw = "// header comment\nMATCH (n)\nRETURN n\nLIMIT 1"
        assert _extract_cypher(raw) == "MATCH (n)\nRETURN n\nLIMIT 1"

    def test_plain_query_unchanged(self) -> None:
        query = "MATCH (e:SecurityEvent) RETURN e LIMIT 5"
        assert _extract_cypher(query) == query


class TestOllamaClientEmbed:
    @pytest.mark.asyncio
    async def test_embed_parses_embeddings_list(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("chat_application.ollama.httpx.AsyncClient", return_value=mock_http):
            vector = await client.embed("hello")

        assert vector == [0.1, 0.2, 0.3]
        assert client.dimension == 3

    @pytest.mark.asyncio
    async def test_embed_falls_back_to_embedding_key(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embedding": [1.0, 2.0]}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=mock_http)

        with patch("chat_application.ollama.httpx.AsyncClient", return_value=mock_http):
            vector = await client.embed("test")

        assert vector == [1.0, 2.0]

    @pytest.mark.asyncio
    async def test_embed_raises_on_unexpected_body(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"unexpected": True}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=mock_http)

        with patch("chat_application.ollama.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(RuntimeError, match="unexpected embed response"):
                await client.embed("bad")


class TestOllamaClientChat:
    @pytest.mark.asyncio
    async def test_chat_returns_content(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": {"content": "  answer text  "}}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=mock_http)

        with patch("chat_application.ollama.httpx.AsyncClient", return_value=mock_http):
            result = await client.chat(system="sys", user="question")

        assert result == "answer text"

    @pytest.mark.asyncio
    async def test_generate_cypher_uses_mode_specific_prompt(self) -> None:
        client = OllamaClient()
        client.chat = AsyncMock(return_value="```\nMATCH (i:Instruction) RETURN i LIMIT 1\n```")

        cypher = await client.generate_cypher("how many?", "schema text", mode="instructions")
        assert cypher == "MATCH (i:Instruction) RETURN i LIMIT 1"
        assert client.chat.await_args is not None
        assert "schema text" in client.chat.await_args.kwargs["user"]

    @pytest.mark.asyncio
    async def test_summarize_authorization_why_falls_back_on_error(self) -> None:
        client = OllamaClient()
        client.chat = AsyncMock(side_effect=httpx.HTTPError("down"))
        result = await client.summarize_authorization_why(
            approver="User A",
            authorization_summary="Raw OPA summary",
        )
        assert result == "Raw OPA summary"
