from __future__ import annotations

import json
import logging
from typing import Any

from neo4j import READ_ACCESS

from chat_application.config import settings
from chat_application.vector.document_ids import (
    event_document_id,
    instruction_document_id,
    payment_document_id,
)

logger = logging.getLogger(__name__)


def _source_filter_values(source: str | None) -> list[str] | None:
    if source is None:
        return None
    if source == "security_events":
        return ["instruction_security_event", "payment_security_event"]
    if source == "payment":
        return ["payment_fact"]
    return [source]


def _payload_from_node(node: dict[str, Any]) -> dict[str, Any]:
    raw = node.get("payload_json")
    if not raw:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


def _allowed_lob_list(allowed_lobs: frozenset[str] | None) -> list[str] | None:
    if allowed_lobs is None:
        return None
    return sorted(allowed_lobs)


class VectorSearchClient:
    """Read path for the Neo4j dense vector store (`MultimodalDocument` nodes)."""

    def __init__(self, neo4j_client) -> None:
        self._neo4j = neo4j_client

    @property
    def _driver(self):
        if self._neo4j._driver is None:
            raise RuntimeError("Neo4j client not connected")
        return self._neo4j._driver

    async def has_documents(self) -> bool:
        count = await self.document_count()
        return count > 0

    async def document_count(self) -> int:
        async with self._driver.session(default_access_mode=READ_ACCESS) as session:
            result = await session.run(
                "MATCH (d:MultimodalDocument) RETURN count(d) AS count"
            )
            record = await result.single()
        return int(record["count"]) if record else 0

    def _to_hit(self, node: dict[str, Any], score: float, source: str) -> dict[str, Any]:
        payload = _payload_from_node(node)
        merged = payload.get("merged")
        if not merged and payload.get("source") in {
            "payment_security_event",
            "payment_fact",
            "instruction_state",
        }:
            merged = payload
        elif not merged:
            merged = {}
        security_event = payload.get("security_event") or {}
        owning_lob = node.get("owning_lob") or payload.get("owning_lob")
        if isinstance(owning_lob, str):
            owning_lob = owning_lob.strip().upper() or None
        else:
            owning_lob = None
        return {
            "source": source,
            "score": float(score),
            "event_id": payload.get("event_id") or node.get("event_id"),
            "instruction_id": payload.get("instruction_id") or node.get("instruction_id"),
            "payment_id": payload.get("payment_id") or node.get("payment_id"),
            "owning_lob": owning_lob,
            "search_text": node.get("search_text") or payload.get("search_text", ""),
            "merged": merged,
            "security_event": security_event,
            "payload": payload,
        }

    async def search_vector(
        self,
        query_vector: list[float],
        *,
        limit: int,
        source: str | None = None,
        allowed_lobs: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        if allowed_lobs is not None and not allowed_lobs:
            return []
        if not await self.has_documents():
            return []
        sources = _source_filter_values(source)
        allowed_list = _allowed_lob_list(allowed_lobs)
        async with self._driver.session(default_access_mode=READ_ACCESS) as session:
            result = await session.run(
                f"""
                CALL db.index.vector.queryNodes(
                  '{settings.multimodal_vector_index}',
                  $limit,
                  $embedding
                )
                YIELD node, score
                WHERE ($sources IS NULL OR node.source IN $sources)
                  AND ($allowed_lobs IS NULL OR node.owning_lob IN $allowed_lobs)
                RETURN node, score
                ORDER BY score DESC
                LIMIT $limit
                """,
                embedding=query_vector,
                limit=limit,
                sources=sources,
                allowed_lobs=allowed_list,
            )
            rows = [record async for record in result]
        return [self._to_hit(dict(row["node"]), float(row["score"]), "vector") for row in rows]

    async def _fetch_document(
        self,
        document_id: str,
        *,
        hit_source: str,
        allowed_lobs: frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        if allowed_lobs is not None and not allowed_lobs:
            return None
        allowed_list = _allowed_lob_list(allowed_lobs)
        async with self._driver.session(default_access_mode=READ_ACCESS) as session:
            result = await session.run(
                """
                MATCH (d:MultimodalDocument {document_id: $document_id})
                WHERE $allowed_lobs IS NULL OR d.owning_lob IN $allowed_lobs
                RETURN d
                """,
                document_id=document_id,
                allowed_lobs=allowed_list,
            )
            record = await result.single()
        if record is None:
            return None
        node = dict(record["d"])
        hit = self._to_hit(node, 1.0, hit_source)
        payload = hit["payload"]
        if hit_source == "exact_instruction":
            hit["merged"] = payload
        if hit_source == "exact_payment":
            hit["merged"] = payload
        if hit_source == "exact":
            hit["instruction"] = payload.get("instruction")
        return hit

    async def fetch_by_event_id(
        self,
        event_id: str,
        *,
        allowed_lobs: frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        return await self._fetch_document(
            event_document_id(event_id),
            hit_source="exact",
            allowed_lobs=allowed_lobs,
        )

    async def fetch_by_instruction_id(
        self,
        instruction_id: str,
        *,
        allowed_lobs: frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        return await self._fetch_document(
            instruction_document_id(instruction_id),
            hit_source="exact_instruction",
            allowed_lobs=allowed_lobs,
        )

    async def fetch_by_payment_id(
        self,
        payment_id: str,
        *,
        allowed_lobs: frozenset[str] | None = None,
    ) -> dict[str, Any] | None:
        return await self._fetch_document(
            payment_document_id(payment_id),
            hit_source="exact_payment",
            allowed_lobs=allowed_lobs,
        )

    async def fetch_instruction_approve_events(
        self,
        instruction_id: str,
        *,
        allowed_lobs: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        if allowed_lobs is not None and not allowed_lobs:
            return []
        allowed_list = _allowed_lob_list(allowed_lobs)
        async with self._driver.session(default_access_mode=READ_ACCESS) as session:
            result = await session.run(
                """
                MATCH (d:MultimodalDocument)
                WHERE d.instruction_id = $instruction_id
                  AND d.source = 'instruction_security_event'
                  AND d.action = 'APPROVE'
                  AND ($allowed_lobs IS NULL OR d.owning_lob IN $allowed_lobs)
                RETURN d
                ORDER BY d.updated_at DESC
                LIMIT 20
                """,
                instruction_id=instruction_id,
                allowed_lobs=allowed_list,
            )
            rows = [record async for record in result]
        return [
            self._to_hit(dict(row["d"]), 1.0, "exact_approve_event")
            for row in rows
        ]

    async def fetch_payment_approve_events(
        self,
        payment_id: str,
        *,
        allowed_lobs: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        if allowed_lobs is not None and not allowed_lobs:
            return []
        allowed_list = _allowed_lob_list(allowed_lobs)
        async with self._driver.session(default_access_mode=READ_ACCESS) as session:
            result = await session.run(
                """
                MATCH (d:MultimodalDocument)
                WHERE d.payment_id = $payment_id
                  AND d.source = 'payment_security_event'
                  AND d.action IN ['APPROVE', 'APPROVE_PAYMENT']
                  AND (d.outcome IS NULL OR d.outcome = 'success')
                  AND ($allowed_lobs IS NULL OR d.owning_lob IN $allowed_lobs)
                RETURN d
                ORDER BY d.updated_at DESC
                LIMIT 20
                """,
                payment_id=payment_id,
                allowed_lobs=allowed_list,
            )
            rows = [record async for record in result]
        return [
            self._to_hit(dict(row["d"]), 1.0, "exact_approve_payment_event")
            for row in rows
        ]
