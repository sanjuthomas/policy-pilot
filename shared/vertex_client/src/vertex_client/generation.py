from __future__ import annotations

import asyncio
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class VertexGenerativeClient:
    """Async wrapper around Vertex AI Gemini text generation."""

    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        model: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._project_id = project_id
        self._region = region
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client: genai.Client | None = None

    @property
    def model(self) -> str:
        return self._model

    async def generate_text(
        self,
        *,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None,
        temperature: float = 0.0,
    ) -> str:
        return await asyncio.to_thread(
            self._generate_sync,
            system,
            user,
            history,
            temperature,
        )

    def _generate_sync(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None,
        temperature: float,
    ) -> str:
        contents: list[types.Content] = []
        for message in history or []:
            role = message.get("role", "user")
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=str(message.get("content", "")))],
                )
            )
        contents.append(types.Content(role="user", parts=[types.Part(text=user)]))

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
        )
        client = self._get_client()
        response = client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("unexpected empty Vertex generate response")
        return text

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._region,
            )
        return self._client

    async def close(self) -> None:
        self._client = None
