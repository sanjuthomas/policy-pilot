from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from typing import Iterator, Literal

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

EmbeddingTaskType = Literal[
    "RETRIEVAL_DOCUMENT",
    "RETRIEVAL_QUERY",
    "SEMANTIC_SIMILARITY",
]


@contextmanager
def _gen_ai_operation(**kwargs) -> Iterator[object | None]:
    try:
        from telemetry.gen_ai import gen_ai_operation

        with gen_ai_operation(**kwargs) as result:
            yield result
    except ImportError:
        yield None


class VertexEmbeddingClient:
    """Async wrapper around Vertex AI text embedding models."""

    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        model: str,
        dimension: int | None = None,
        document_task_type: EmbeddingTaskType = "RETRIEVAL_DOCUMENT",
        query_task_type: EmbeddingTaskType = "RETRIEVAL_QUERY",
    ) -> None:
        self._project_id = project_id
        self._region = region
        self._model = model
        self._configured_dimension = dimension
        self._dimension: int | None = dimension
        self._document_task_type = document_task_type
        self._query_task_type = query_task_type
        self._client: genai.Client | None = None
        self._ready = False

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            raise RuntimeError("Vertex embedding dimension not initialized")
        return self._dimension

    async def embed(
        self,
        text: str,
        *,
        task_type: EmbeddingTaskType | None = None,
    ) -> list[float]:
        if not text.strip():
            raise ValueError("cannot embed empty text")

        task = task_type or self._document_task_type
        try:
            from telemetry.gen_ai import summarize_embedding_request
        except ImportError:
            summarize_embedding_request = lambda value: f"text_chars={len(value)}"  # noqa: E731

        with _gen_ai_operation(
            operation="embeddings",
            model=self._model,
            request_summary=summarize_embedding_request(text),
        ) as telemetry_result:
            vector = await asyncio.to_thread(self._embed_sync, text, task)
            if self._dimension is None:
                self._dimension = len(vector)
            elif len(vector) != self._dimension:
                raise RuntimeError(
                    f"embedding dimension mismatch: expected {self._dimension}, got {len(vector)}"
                )
            if telemetry_result is not None:
                telemetry_result.response_text = f"vector_dim={len(vector)}"
                telemetry_result.attributes["gen_ai.embeddings.dimension"] = str(len(vector))
            return vector

    async def embed_query(self, text: str) -> list[float]:
        return await self.embed(text, task_type=self._query_task_type)

    def _embed_sync(self, text: str, task_type: EmbeddingTaskType) -> list[float]:
        config_kwargs: dict[str, object] = {"task_type": task_type}
        if self._configured_dimension is not None and self._model.startswith("gemini-embedding"):
            config_kwargs["output_dimensionality"] = self._configured_dimension

        config = types.EmbedContentConfig(**config_kwargs)
        client = self._get_client()
        response = client.models.embed_content(
            model=self._model,
            contents=text,
            config=config,
        )
        embeddings = response.embeddings
        if not embeddings or not embeddings[0].values:
            raise RuntimeError("unexpected empty Vertex embed response")
        return [float(value) for value in embeddings[0].values]

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                vertexai=True,
                project=self._project_id,
                location=self._region,
            )
        return self._client

    async def warmup(self) -> None:
        await self.embed("warmup")
        self._ready = True
        logger.info(
            "Vertex embeddings ready model=%s dimension=%s",
            self._model,
            self._dimension,
        )

    async def close(self) -> None:
        self._client = None
