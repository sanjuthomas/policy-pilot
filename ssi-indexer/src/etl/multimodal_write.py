from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

MULTIMODAL_UPSERT_CYPHER = """
MERGE (d:MultimodalDocument {document_id: $document_id})
SET d.search_text = $search_text,
    d.embedding = $embedding,
    d.payload_json = $payload_json,
    d.source = $source,
    d.event_id = $event_id,
    d.instruction_id = $instruction_id,
    d.payment_id = $payment_id,
    d.action = $action,
    d.outcome = $outcome,
    d.updated_at = datetime()
"""


@dataclass(frozen=True)
class MultimodalWrite:
    """Prepared multimodal document to commit in the same Neo4j tx as graph writes."""

    document_id: str
    search_text: str
    payload: dict[str, Any]
    dense_vector: list[float]


def multimodal_upsert_params(write: MultimodalWrite) -> dict[str, Any]:
    payload = dict(write.payload)
    fields = _denormalized_fields(payload)
    return {
        "document_id": write.document_id,
        "search_text": write.search_text,
        "embedding": write.dense_vector,
        "payload_json": json.dumps(payload, default=str),
        "source": payload.get("source"),
        "event_id": fields.get("event_id"),
        "instruction_id": fields.get("instruction_id"),
        "payment_id": fields.get("payment_id"),
        "action": fields.get("action"),
        "outcome": fields.get("outcome"),
    }


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


async def upsert_multimodal_in_tx(tx: Any, write: MultimodalWrite) -> None:
    await tx.run(MULTIMODAL_UPSERT_CYPHER, **multimodal_upsert_params(write))


async def upsert_multimodal_writes_in_tx(
    tx: Any,
    primary: MultimodalWrite | None,
    extra: list[MultimodalWrite] | None = None,
) -> None:
    if primary is not None:
        await upsert_multimodal_in_tx(tx, primary)
    for write in extra or []:
        await upsert_multimodal_in_tx(tx, write)
