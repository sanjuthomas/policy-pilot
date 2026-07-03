from __future__ import annotations

import logging
from typing import Any

from etl.enrichment import enrich_document
from etl.multimodal_store import MultimodalNeo4jStore, event_document_id
from etl.multimodal_write import MultimodalWrite
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

        if not self._multimodal_ready:
            await self.ollama_client.warmup()
            await self.multimodal_store.ensure_indexes(self.ollama_client.dimension)
            self._multimodal_ready = True

        dense_vector = await self.ollama_client.embed(document.search_text)
        event_payload = document.model_dump(mode="json")
        event_payload["source"] = "instruction_security_event"
        multimodal = MultimodalWrite(
            document_id=event_document_id(document.event_id),
            search_text=document.search_text,
            payload=event_payload,
            dense_vector=dense_vector,
        )

        extra_multimodal: list[MultimodalWrite] = []
        event_ctx = security_event.get("event") or {}
        if event_ctx.get("action") == "APPROVE" and document.instruction_id:
            auth = (security_event.get("details") or {}).get("authorization") or {}
            summary = auth.get("summary")
            if summary:
                snap = security_event.get("instruction_snapshot") or {}
                patch = await self.multimodal_store.build_instruction_state_authorization_patch(
                    document.instruction_id,
                    approved_at=snap.get("approved_at"),
                    authorization_summary=summary,
                    authorization_basis=auth.get("allow_basis") or [],
                )
                if patch:
                    patch_id, patch_text, patch_payload = patch
                    patch_vector = await self.ollama_client.embed(patch_text)
                    extra_multimodal.append(
                        MultimodalWrite(
                            document_id=patch_id,
                            search_text=patch_text,
                            payload=patch_payload,
                            dense_vector=patch_vector,
                        )
                    )

        await self.neo4j_writer.upsert(
            document,
            multimodal=multimodal,
            extra_multimodal=extra_multimodal or None,
        )

        logger.info(
            "processed instruction security event event_id=%s instruction_id=%s",
            document.event_id,
            document.instruction_id,
        )
