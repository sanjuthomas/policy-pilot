from __future__ import annotations

import json
import logging

import httpx
from cypher_gen import cypher_system_prompt, extract_cypher

from etl.config import settings

logger = logging.getLogger(__name__)


class OllamaChatClient:
    """Local Ollama HTTP client for LLM Cypher generation (embeddings use Vertex AI)."""

    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=settings.ollama_timeout_seconds)
        return self._http

    async def close(self) -> None:
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    async def chat(
        self,
        *,
        system: str,
        user: str,
    ) -> str:
        client = await self._client()
        response = await client.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_chat_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            },
        )
        response.raise_for_status()
        body = response.json()
        message = body.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise RuntimeError(f"unexpected Ollama chat response: {json.dumps(body)[:300]}")
        return str(content).strip()

    async def generate_cypher(
        self,
        question: str,
        schema: str,
        *,
        mode: str = "events",
    ) -> str:
        system = cypher_system_prompt(mode)
        user_prompt = f"""Graph schema documentation:

{schema}

Question: {question}

Cypher:"""
        raw = await self.chat(system=system, user=user_prompt)
        return extract_cypher(raw)
