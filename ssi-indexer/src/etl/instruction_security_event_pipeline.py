from __future__ import annotations

import logging
from typing import Any

from etl.enrichment import enrich_document
from etl.multimodal_store import MultimodalNeo4jStore
from etl.neo4j_client import Neo4jGraphWriter
from etl.ollama_client import OllamaEmbeddingClient

logger = logging.getLogger(__name__)


class InstructionSecurityEventPipeline:
    """Processes instruction security event facts from the instruction_security_events topic.

    Each event is self-contained (instruction_snapshot embedded) — no API calls.
    """

    def __init__(
        self,
        *,
        neo4j_writer: Neo4jGraphWriter,
        ollama_client: OllamaEmbeddingClient,
        multimodal_store: MultimodalNeo4jStore,
    ) -> None:
        self.neo4j_writer = neo4j_writer
        self.ollama_client = ollama_client
        self.multimodal_store = multimodal_store
        self._multimodal_ready = False

    async def process_instruction_security_event(self, security_event: dict[str, Any]) -> None:
        # instruction_snapshot is embedded in the event — no API call needed
        instruction = security_event.get("instruction_snapshot")
        document = enrich_document(security_event, instruction)

        await self.neo4j_writer.upsert(document)

        if not self._multimodal_ready:
            await self.ollama_client.warmup()
            await self.multimodal_store.ensure_indexes(self.ollama_client.dimension)
            self._multimodal_ready = True

        dense_vector = await self.ollama_client.embed(document.search_text)
        await self.multimodal_store.upsert(document, dense_vector=dense_vector)

        event_ctx = security_event.get("event") or {}
        if event_ctx.get("action") == "APPROVE":
            auth = (security_event.get("details") or {}).get("authorization") or {}
            summary = auth.get("summary")
            if summary:
                snap = security_event.get("instruction_snapshot") or {}
                await self.multimodal_store.patch_instruction_state_authorization(
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
