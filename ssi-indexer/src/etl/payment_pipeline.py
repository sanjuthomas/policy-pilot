"""Processes payment events from the payment_security_events and payments topics.

Two sub-pipelines:
  PaymentSecurityEventPipeline  — consumes payment_security_events
  PaymentFactPipeline           — consumes payments
"""
from __future__ import annotations

import json
import logging
from typing import Any

from vertex_client import VertexEmbeddingClient

from etl.authorization_context import authorization_merged_fields
from etl.multimodal_store import (
    MultimodalNeo4jStore,
    event_document_id,
    payment_document_id,
)
from etl.multimodal_write import MultimodalWrite
from etl.neo4j_client import Neo4jGraphWriter
from etl.search_text.builder import build_search_text_from_profile
from etl.search_text.context import payment_security_event_context

logger = logging.getLogger(__name__)


def _display(user: dict[str, Any], prefix: str = "") -> str:
    fn = user.get(f"{prefix}family_name") or user.get("family_name") or ""
    gn = user.get(f"{prefix}given_name") or user.get("given_name") or ""
    uid = user.get(f"{prefix}user_id") or user.get("user_id") or ""
    if fn and gn:
        return f"{fn}, {gn} ({uid})"
    return uid


def _roles_json(roles: list | None) -> str | None:
    if not roles:
        return None
    return json.dumps(roles)


def build_payment_event_search_text(event: dict[str, Any]) -> str:
    return build_search_text_from_profile(
        "payment_security_event",
        payment_security_event_context(event),
    )


def build_payment_fact_search_text(fact: dict[str, Any]) -> str:
    return build_search_text_from_profile("payment_fact", fact)


class PaymentSecurityEventPipeline:
    """Processes PaymentSecurityEvent messages from payment_security_events topic."""

    def __init__(
        self,
        *,
        neo4j_writer: Neo4jGraphWriter,
        embedding_client: VertexEmbeddingClient,
        multimodal_store: MultimodalNeo4jStore,
    ) -> None:
        self.neo4j_writer = neo4j_writer
        self.embedding_client = embedding_client
        self.multimodal_store = multimodal_store
        self._multimodal_ready = False

    async def process(self, event: dict[str, Any]) -> None:
        event_id = event.get("event_id")
        if not event_id:
            logger.warning("payment security event missing event_id — skipping")
            return

        if not self._multimodal_ready:
            await self.embedding_client.warmup()
            await self.multimodal_store.ensure_indexes(self.embedding_client.dimension)
            self._multimodal_ready = True

        search_text = build_payment_event_search_text(event)
        dense_vector = await self.embedding_client.embed(search_text)

        resource = event.get("resource") or {}
        actor = event.get("actor") or {}
        event_ctx = event.get("event") or {}
        snap = event.get("payment_snapshot") or {}
        created_by = snap.get("created_by") or {}

        auth_ctx = authorization_merged_fields(event)
        payload = {
            "event_id": event_id,
            "payment_id": resource.get("id"),
            "instruction_id": resource.get("instruction_id"),
            "source": "payment_security_event",
            "search_text": search_text,
            "timestamp": event.get("timestamp"),
            "severity": event.get("severity"),
            "message": event.get("message"),
            "action": event_ctx.get("action"),
            "outcome": event_ctx.get("outcome"),
            "reason": event_ctx.get("reason"),
            "amount": resource.get("amount"),
            "currency": resource.get("currency"),
            "owning_lob": resource.get("owning_lob"),
            "actor_user_id": actor.get("user_id"),
            "actor_display": _display(actor),
            "creator_user_id": created_by.get("user_id"),
            "creator_display": _display(created_by),
            **auth_ctx,
            "security_event": event,
        }

        multimodal = MultimodalWrite(
            document_id=event_document_id(event_id),
            search_text=search_text,
            payload=payload,
            dense_vector=dense_vector,
        )
        await self.neo4j_writer.upsert_payment_security_event(event, multimodal=multimodal)

        logger.info(
            "processed payment security event event_id=%s payment_id=%s",
            event_id,
            resource.get("id"),
        )


class PaymentFactPipeline:
    """Processes payment fact snapshots from the payments topic."""

    def __init__(
        self,
        *,
        neo4j_writer: Neo4jGraphWriter,
        embedding_client: VertexEmbeddingClient,
        multimodal_store: MultimodalNeo4jStore,
    ) -> None:
        self.neo4j_writer = neo4j_writer
        self.embedding_client = embedding_client
        self.multimodal_store = multimodal_store
        self._multimodal_ready = False

    async def process(self, fact: dict[str, Any]) -> None:
        payment_id = fact.get("payment_id")
        if not payment_id:
            logger.warning("payment fact missing payment_id — skipping")
            return

        if not self._multimodal_ready:
            await self.embedding_client.warmup()
            await self.multimodal_store.ensure_indexes(self.embedding_client.dimension)
            self._multimodal_ready = True

        search_text = build_payment_fact_search_text(fact)
        dense_vector = await self.embedding_client.embed(search_text)

        created_by = fact.get("created_by") or {}
        approved_by = fact.get("approved_by") or {}

        payload = {
            "payment_id": payment_id,
            "instruction_id": fact.get("instruction_id"),
            "status": fact.get("status"),
            "amount": fact.get("amount"),
            "currency": fact.get("currency"),
            "value_date": fact.get("value_date"),
            "owning_lob": fact.get("owning_lob"),
            "instruction_type": fact.get("instruction_type"),
            "creator_user_id": created_by.get("user_id"),
            "creator_display": _display(created_by),
            "approver_user_id": approved_by.get("user_id"),
            "approver_display": _display(approved_by),
            "source": "payment_fact",
            "search_text": search_text,
            "payment_snapshot": fact,
        }

        multimodal = MultimodalWrite(
            document_id=payment_document_id(payment_id),
            search_text=search_text,
            payload=payload,
            dense_vector=dense_vector,
        )
        await self.neo4j_writer.upsert_payment_fact(fact, multimodal=multimodal)

        logger.info(
            "processed payment fact payment_id=%s status=%s",
            payment_id,
            fact.get("status"),
        )
