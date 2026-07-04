from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_application.ollama import OllamaCypherClient
from cypher_gen import extract_cypher


class TestExtractCypher:
    def test_strips_markdown_fence(self) -> None:
        raw = """```cypher
MATCH (n) RETURN n LIMIT 1
```"""
        assert extract_cypher(raw) == "MATCH (n) RETURN n LIMIT 1"

    def test_removes_comment_lines(self) -> None:
        raw = "// header comment\nMATCH (n)\nRETURN n\nLIMIT 1"
        assert extract_cypher(raw) == "MATCH (n)\nRETURN n\nLIMIT 1"

    def test_plain_query_unchanged(self) -> None:
        query = "MATCH (e:SecurityEvent) RETURN e LIMIT 5"
        assert extract_cypher(query) == query


class TestOllamaCypherClientChat:
    @pytest.mark.asyncio
    async def test_chat_returns_content(self) -> None:
        client = OllamaCypherClient()
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
        client = OllamaCypherClient()
        client.chat = AsyncMock(return_value="```\nMATCH (i:Instruction) RETURN i LIMIT 1\n```")

        cypher = await client.generate_cypher("how many?", "schema text", mode="instructions")
        assert cypher == "MATCH (i:Instruction) RETURN i LIMIT 1"
        assert client.chat.await_args is not None
        assert "schema text" in client.chat.await_args.kwargs["user"]

    @pytest.mark.asyncio
    async def test_chat_raises_on_unexpected_body(self) -> None:
        client = OllamaCypherClient()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"unexpected": True}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=mock_http)

        with patch("chat_application.ollama.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(RuntimeError, match="unexpected Ollama chat response"):
                await client.chat(system="sys", user="question")
