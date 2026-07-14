from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from typing import Iterator

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


@contextmanager
def _gen_ai_operation(**kwargs) -> Iterator[object | None]:
    try:
        from telemetry.gen_ai import gen_ai_operation

        with gen_ai_operation(**kwargs) as result:
            yield result
    except ImportError:
        yield None


class VertexGenerativeClient:
    """Async wrapper around Vertex AI Gemini text generation."""

    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        model: str,
    ) -> None:
        self._project_id = project_id
        self._region = region
        self._model = model
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
        response_schema: dict | None = None,
    ) -> str:
        try:
            from telemetry.gen_ai import summarize_generation_request
        except ImportError:
            summarize_generation_request = lambda **kwargs: "generation_request"  # noqa: E731

        with _gen_ai_operation(
            operation="chat",
            model=self._model,
            request_summary=summarize_generation_request(
                system=system,
                user=user,
                history=history,
            ),
        ) as telemetry_result:
            text, input_tokens, output_tokens = await asyncio.to_thread(
                self._generate_sync,
                system,
                user,
                history,
                temperature,
                response_schema,
            )
            if telemetry_result is not None:
                telemetry_result.response_text = text
                telemetry_result.input_tokens = input_tokens
                telemetry_result.output_tokens = output_tokens
            return text

    def _generate_sync(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None,
        temperature: float,
        response_schema: dict | None,
    ) -> tuple[str, int | None, int | None]:
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
        if response_schema is not None:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema

        client = self._get_client()
        response = client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("unexpected empty Vertex generate response")

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        return text, input_tokens, output_tokens

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
