from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument

from ps.config import settings
from ps.database import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def serialize_audit_execution(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    document_id = out.pop("_id", None)
    if document_id is not None and "execution_id" not in out:
        out["execution_id"] = str(document_id)
    for key in ("created_at", "updated_at"):
        value = out.get(key)
        if isinstance(value, datetime):
            out[key] = value.isoformat() + "Z"
    timeline = out.get("timeline")
    if isinstance(timeline, list):
        serialized_steps: list[dict[str, Any]] = []
        for step in timeline:
            if not isinstance(step, dict):
                continue
            item = dict(step)
            at = item.get("at")
            if isinstance(at, datetime):
                item["at"] = at.isoformat() + "Z"
            serialized_steps.append(item)
        out["timeline"] = serialized_steps
    return out


class AuditExecutionRepository:
    """Append-oriented governed-activity evidence (links to security events for OPA)."""

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return get_db()[settings.audit_executions_collection]

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        execution_id = str(document.get("execution_id") or f"AUD-{uuid4()}")
        payload = dict(document)
        payload["_id"] = execution_id
        payload["execution_id"] = execution_id
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        await self.collection.insert_one(payload)
        return serialize_audit_execution(payload)

    async def get(self, execution_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"_id": execution_id})
        if doc is None:
            return None
        return serialize_audit_execution(doc)

    async def list_recent(
        self, *, limit: int = 100, actor_user_id: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if actor_user_id is not None:
            query["actor.user_id"] = actor_user_id
        docs = [
            doc
            async for doc in self.collection.find(query).sort("created_at", -1).limit(limit)
        ]
        return [serialize_audit_execution(doc) for doc in docs]

    async def patch(
        self,
        execution_id: str,
        updates: dict[str, Any],
        *,
        expected_actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        query: dict[str, Any] = {"_id": execution_id}
        if expected_actor_user_id is not None:
            query["actor.user_id"] = expected_actor_user_id

        set_fields = {key: value for key, value in updates.items() if value is not None}
        set_fields["updated_at"] = _utcnow()

        unset_fields: dict[str, str] = {}
        if "governance" in set_fields and isinstance(set_fields["governance"], dict):
            governance = dict(set_fields["governance"])
            if governance.get("security_event_id"):
                # Prefer the security-event OPA record; drop provisional exchange.
                unset_fields["governance.policy_exchange"] = ""
            set_fields["governance"] = governance

        update_doc: dict[str, Any] = {"$set": set_fields}
        if unset_fields:
            update_doc["$unset"] = unset_fields

        doc = await self.collection.find_one_and_update(
            query,
            update_doc,
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            return None
        return serialize_audit_execution(doc)

    async def link_security_event(
        self,
        execution_id: str,
        *,
        security_event_id: str,
        payment_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        query: dict[str, Any] = {"_id": execution_id}
        if actor_user_id is not None:
            query["actor.user_id"] = actor_user_id

        set_fields: dict[str, Any] = {
            "governance.security_event_id": security_event_id,
            "updated_at": _utcnow(),
            "status": "COMPLETED",
            "outcome": "allow",
        }
        if payment_id is not None:
            set_fields["result.payment_id"] = payment_id

        doc = await self.collection.find_one_and_update(
            query,
            {
                "$set": set_fields,
                "$unset": {"governance.policy_exchange": ""},
            },
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            return None
        return serialize_audit_execution(doc)
