from __future__ import annotations

import logging
from typing import Any

from etl.enrichment import enrich_document
from etl.neo4j_client import Neo4jGraphWriter
from etl.ollama_client import OllamaEmbeddingClient
from etl.qdrant_store import QdrantHybridStore

logger = logging.getLogger(__name__)


class InstructionSecurityEventPipeline:
    """Processes instruction security event facts from the instruction-security-events topic.

    Each event is self-contained (instruction_snapshot embedded) — no API calls.
    """

    def __init__(
        self,
        *,
        neo4j_writer: Neo4jGraphWriter,
        ollama_client: OllamaEmbeddingClient,
        qdrant_store: QdrantHybridStore,
    ) -> None:
        self.neo4j_writer = neo4j_writer
        self.ollama_client = ollama_client
        self.qdrant_store = qdrant_store
        self._qdrant_ready = False

    async def process_instruction_security_event(self, security_event: dict[str, Any]) -> None:
        # instruction_snapshot is embedded in the event — no API call needed
        instruction = security_event.get("instruction_snapshot")
        document = enrich_document(security_event, instruction)

        await self.neo4j_writer.upsert(document)

        if not self._qdrant_ready:
            await self.ollama_client.warmup()
            self.qdrant_store.ensure_collection(self.ollama_client.dimension)
            self._qdrant_ready = True

        dense_vector = await self.ollama_client.embed(document.search_text)
        self.qdrant_store.upsert(document, dense_vector=dense_vector)

        event_ctx = security_event.get("event") or {}
        if event_ctx.get("action") == "APPROVE":
            auth = (security_event.get("details") or {}).get("authorization") or {}
            summary = auth.get("summary")
            if summary:
                snap = security_event.get("instruction_snapshot") or {}
                self.qdrant_store.patch_instruction_state_authorization(
                    document.instruction_id,
                    approved_at=snap.get("approved_at"),
                    authorization_summary=summary,
                    authorization_basis=auth.get("allow_basis") or [],
                )

        logger.info(
            "processed instruction security event event_id=%s instruction_id=%s",
            document.event_id,
            document.instruction_id,
        )
