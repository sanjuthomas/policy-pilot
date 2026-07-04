from __future__ import annotations

import logging

from cypher_builder import (
    GRAPH_QUERY_EXTRACTION_SYSTEM,
    GraphQueryPlan,
    build_extraction_user_prompt,
    parse_graph_query_plan,
)
from vertex_client import VertexEmbeddingClient, VertexGenerativeClient

from chat_application.prompts import (
    AUTHORIZATION_WHY_SUMMARY_SYSTEM_PROMPT,
    answer_system_prompt,
)

logger = logging.getLogger(__name__)


class PolicyPilotMlClient:
    """Vertex embeddings + Gemini for synthesis and structured graph plan extraction."""

    def __init__(
        self,
        *,
        embedding_client: VertexEmbeddingClient | None = None,
        generation_client: VertexGenerativeClient | None = None,
    ) -> None:
        from chat_application.config import settings

        self._embedding = embedding_client or VertexEmbeddingClient(
            project_id=settings.gcp_project_id,
            region=settings.gcp_region,
            model=settings.vertex_embedding_model,
            dimension=settings.embedding_dimension,
        )
        self._generation = generation_client or VertexGenerativeClient(
            project_id=settings.gcp_project_id,
            region=settings.gcp_region,
            model=settings.vertex_gemini_model,
            timeout_seconds=settings.vertex_timeout_seconds,
        )

    @property
    def dimension(self) -> int:
        return self._embedding.dimension

    async def embed(self, text: str) -> list[float]:
        return await self._embedding.embed_query(text)

    async def warmup(self) -> None:
        await self._embedding.warmup()

    async def extract_graph_query_plan(
        self,
        question: str,
        *,
        mode: str = "events",
    ) -> GraphQueryPlan:
        raw = await self._generation.generate_text(
            system=GRAPH_QUERY_EXTRACTION_SYSTEM,
            user=build_extraction_user_prompt(question=question, mode=mode),
            temperature=0.0,
        )
        return parse_graph_query_plan(raw)

    async def synthesize_answer(
        self,
        question: str,
        context: str,
        history: list[dict[str, str]] | None = None,
        *,
        mode: str = "events",
    ) -> str:
        system = answer_system_prompt(mode)
        user_prompt = f"""Context:

{context}

Question: {question}"""
        return await self._generation.generate_text(
            system=system,
            user=user_prompt,
            history=history,
        )

    async def summarize_authorization_why(
        self,
        *,
        approver: str,
        authorization_summary: str,
        authorization_basis: list[str] | None = None,
    ) -> str:
        basis_block = ""
        if authorization_basis:
            basis_block = "\nPolicy basis points:\n" + "\n".join(
                f"- {point}" for point in authorization_basis
            )

        user_prompt = f"""Approver: {approver}

OPA authorization summary:
{authorization_summary}
{basis_block}

Rewrite the authorization reason in clear English:"""

        try:
            rewritten = await self._generation.generate_text(
                system=AUTHORIZATION_WHY_SUMMARY_SYSTEM_PROMPT,
                user=user_prompt,
            )
            if rewritten:
                return rewritten.strip()
        except Exception as exc:
            logger.warning("authorization why summarization failed: %s", exc)

        return authorization_summary.strip()

    async def close(self) -> None:
        await self._embedding.close()
        await self._generation.close()
