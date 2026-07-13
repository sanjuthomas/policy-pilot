from __future__ import annotations

import json
import logging
import statistics
import uuid
from typing import Any

from etl.config import settings
from etl.enrichment import EnrichedSecurityEventDocument
from etl.multimodal_write import (
    MultimodalWrite,
    upsert_multimodal_in_tx,
)
from etl.neo4j_client import Neo4jGraphWriter

logger = logging.getLogger(__name__)

INDEXING_MODEL = "one_point_per_record"


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text.split()) * 1.3))


def _numeric_summary(values: list[int]) -> dict[str, int | float]:
    if not values:
        return {"min": 0, "max": 0, "avg": 0, "median": 0}
    return {
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values)),
        "median": int(statistics.median(values)),
    }


def _chunk_record_id(payload: dict[str, Any]) -> str | None:
    return (
        payload.get("event_id")
        or payload.get("payment_id")
        or payload.get("instruction_id")
    )


def event_document_id(event_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, event_id))


def instruction_document_id(instruction_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"instruction:{instruction_id}"))


def payment_document_id(payment_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"payment:{payment_id}"))


def _payload_from_node(node: dict[str, Any]) -> dict[str, Any]:
    raw = node.get("payload_json")
    if not raw:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


def _denormalized_fields(payload: dict[str, Any]) -> dict[str, Any]:
    merged = payload.get("merged") or {}
    security_event = payload.get("security_event") or {}
    event_ctx = security_event.get("event") or {}
    return {
        "event_id": payload.get("event_id"),
        "instruction_id": payload.get("instruction_id"),
        "payment_id": payload.get("payment_id"),
        "action": payload.get("action") or merged.get("action") or event_ctx.get("action"),
        "outcome": payload.get("outcome") or merged.get("outcome") or event_ctx.get("outcome"),
    }


def _node_to_result(node: dict[str, Any], score: float) -> dict[str, Any]:
    payload = _payload_from_node(node)
    return {
        "score": score,
        "event_id": payload.get("event_id") or node.get("event_id"),
        "instruction_id": payload.get("instruction_id") or node.get("instruction_id"),
        "search_text": node.get("search_text") or payload.get("search_text"),
        "security_event": payload.get("security_event"),
        "payload": payload,
    }


def _source_filter_values(source: str | None) -> list[str] | None:
    if source is None:
        return None
    if source == "security_events":
        return ["instruction_security_event", "payment_security_event"]
    if source == "payment":
        return ["payment_fact"]
    return [source]


class MultimodalNeo4jStore:
    """Neo4j-backed multimodal store — dense vector search."""

    def __init__(self, neo4j_writer: Neo4jGraphWriter) -> None:
        self._writer = neo4j_writer
        self._indexes_ready = False

    @property
    def _driver(self):
        if self._writer._driver is None:
            raise RuntimeError("Neo4j driver not connected")
        return self._writer._driver

    async def ensure_indexes(self, dense_dimension: int) -> None:
        if self._indexes_ready:
            return

        vector_index = settings.multimodal_vector_index
        statements = [
            f"""
            CREATE VECTOR INDEX {vector_index} IF NOT EXISTS
            FOR (d:MultimodalDocument) ON (d.embedding)
            OPTIONS {{
              indexConfig: {{
                `vector.dimensions`: {dense_dimension},
                `vector.similarity_function`: 'cosine'
              }}
            }}
            """,
        ]
        async with self._driver.session() as session:
            for statement in statements:
                try:
                    await session.run(statement)
                except Exception as exc:
                    logger.warning("multimodal index statement failed: %s", exc)
        self._indexes_ready = True
        logger.info(
            "multimodal store indexes ready vector=%s dim=%s",
            vector_index,
            dense_dimension,
        )

    async def has_documents(self) -> bool:
        count = await self.document_count()
        return count > 0

    async def document_count(self) -> int:
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (d:MultimodalDocument) RETURN count(d) AS count"
            )
            record = await result.single()
        return int(record["count"]) if record else 0

    async def _upsert(
        self,
        *,
        document_id: str,
        search_text: str,
        payload: dict[str, Any],
        dense_vector: list[float],
    ) -> None:
        write = MultimodalWrite(
            document_id=document_id,
            search_text=search_text,
            payload=dict(payload),
            dense_vector=dense_vector,
        )
        async with self._driver.session() as session:
            tx = await session.begin_transaction()
            try:
                await upsert_multimodal_in_tx(tx, write)
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

    async def upsert(
        self,
        document: EnrichedSecurityEventDocument,
        *,
        dense_vector: list[float],
    ) -> None:
        payload = document.model_dump(mode="json")
        payload["source"] = "instruction_security_event"
        await self._upsert(
            document_id=event_document_id(document.event_id),
            search_text=document.search_text,
            payload=payload,
            dense_vector=dense_vector,
        )

    async def upsert_payment_point(
        self,
        point_id: str,
        search_text: str,
        payload: dict,
        *,
        dense_vector: list[float],
    ) -> None:
        await self._upsert(
            document_id=point_id,
            search_text=search_text,
            payload=dict(payload),
            dense_vector=dense_vector,
        )

    async def upsert_instruction_state(
        self,
        instruction_id: str,
        search_text: str,
        payload: dict,
        *,
        dense_vector: list[float],
    ) -> None:
        payload = dict(payload)
        payload["source"] = "instruction_state"
        payload["instruction_id"] = instruction_id
        await self._upsert(
            document_id=instruction_document_id(instruction_id),
            search_text=search_text,
            payload=payload,
            dense_vector=dense_vector,
        )

    async def get_instruction_state_payload(self, instruction_id: str) -> dict[str, Any] | None:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (d:MultimodalDocument {document_id: $document_id})
                RETURN d
                """,
                document_id=instruction_document_id(instruction_id),
            )
            record = await result.single()
        if record is None:
            return None
        return _payload_from_node(dict(record["d"]))

    async def build_instruction_state_authorization_patch(
        self,
        instruction_id: str,
        *,
        approved_at: str | None,
        authorization_summary: str | None,
        authorization_basis: list[str] | None,
    ) -> tuple[str, str, dict[str, Any]] | None:
        """Return document id, search text, and payload for an instruction_state upsert."""
        if not authorization_summary:
            return None

        document_id = instruction_document_id(instruction_id)
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (d:MultimodalDocument {document_id: $document_id})
                RETURN d
                """,
                document_id=document_id,
            )
            record = await result.single()
        if record is None:
            return None

        node = dict(record["d"])
        payload = _payload_from_node(node)
        basis = list(authorization_basis or [])
        payload["approved_at"] = approved_at or payload.get("approved_at")
        payload["authorization_summary"] = authorization_summary
        payload["authorization_basis"] = basis
        payload["source"] = "instruction_state"
        payload["instruction_id"] = instruction_id
        extra = " ".join(
            part
            for part in [approved_at or "", authorization_summary, " ".join(basis)]
            if part
        )
        search_text = node.get("search_text") or payload.get("search_text") or ""
        if extra:
            search_text = f"{search_text} {extra}".strip()
        return document_id, search_text, payload

    async def search_dense(
        self,
        query_vector: list[float],
        *,
        limit: int,
        source: str | None = None,
    ) -> list[dict]:
        sources = _source_filter_values(source)
        async with self._driver.session() as session:
            result = await session.run(
                f"""
                CALL db.index.vector.queryNodes(
                  '{settings.multimodal_vector_index}',
                  $limit,
                  $embedding
                )
                YIELD node, score
                WHERE $sources IS NULL OR node.source IN $sources
                RETURN node, score
                ORDER BY score DESC
                LIMIT $limit
                """,
                embedding=query_vector,
                limit=limit,
                sources=sources,
            )
            rows = [record async for record in result]
        if rows:
            return [_node_to_result(dict(row["node"]), float(row["score"])) for row in rows]
        return []

    async def search_text_chunk_stats(self, *, top_n: int = 10) -> dict[str, Any]:
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (d:MultimodalDocument)
                RETURN d.document_id AS document_id,
                       d.source AS source,
                       d.event_id AS event_id,
                       d.instruction_id AS instruction_id,
                       d.payment_id AS payment_id,
                       d.search_text AS search_text
                """
            )
            records = [record async for record in result]

        rows: list[dict[str, Any]] = []
        for record in records:
            text = str(record.get("search_text") or "")
            payload = {
                "event_id": record.get("event_id"),
                "instruction_id": record.get("instruction_id"),
                "payment_id": record.get("payment_id"),
            }
            rows.append(
                {
                    "point_id": record.get("document_id"),
                    "source": record.get("source") or "unknown",
                    "event_id": record.get("event_id"),
                    "instruction_id": record.get("instruction_id"),
                    "payment_id": record.get("payment_id"),
                    "record_id": _chunk_record_id(payload),
                    "char_count": len(text),
                    "word_count": len(text.split()),
                    "estimated_tokens": _estimate_tokens(text),
                    "preview": text[:240].replace("\n", " "),
                }
            )

        char_counts = [row["char_count"] for row in rows]
        word_counts = [row["word_count"] for row in rows]
        token_counts = [row["estimated_tokens"] for row in rows]

        by_source: dict[str, dict[str, int | float]] = {}
        for source in {row["source"] for row in rows}:
            source_chars = [row["char_count"] for row in rows if row["source"] == source]
            by_source[source] = {
                "count": len(source_chars),
                "max_chars": max(source_chars) if source_chars else 0,
                "avg_chars": round(sum(source_chars) / len(source_chars)) if source_chars else 0,
            }

        top_chunks = sorted(rows, key=lambda row: row["estimated_tokens"], reverse=True)[:top_n]
        for index, row in enumerate(top_chunks, start=1):
            row["rank"] = index

        return {
            "store": "neo4j_multimodal",
            "indexing_model": INDEXING_MODEL,
            "points_count": len(rows),
            "search_text_field": "search_text",
            "summary": {
                "char_count": _numeric_summary(char_counts),
                "word_count": _numeric_summary(word_counts),
                "estimated_tokens": _numeric_summary(token_counts),
            },
            "by_source": by_source,
            "top_chunks": top_chunks,
        }
