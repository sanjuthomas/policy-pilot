from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from bson import ObjectId

from audit_console.config import settings
from audit_console.database import audit_db, security_events_db

EventSource = Literal["instruction", "payment"]


def normalize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat() + ("Z" if value.tzinfo is None else "")
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def event_collection_name(source: EventSource) -> str:
    if source == "instruction":
        return settings.instruction_events_collection
    return settings.payment_events_collection


def serialize_event(document: dict[str, Any], source: EventSource) -> dict[str, Any]:
    event = normalize(document)
    event["event_id"] = str(event.get("_id") or event.get("event_id") or "")
    event["domain"] = source
    return event


def serialize_execution(document: dict[str, Any]) -> dict[str, Any]:
    execution = normalize(document)
    execution["execution_id"] = str(
        execution.get("execution_id") or execution.get("_id") or ""
    )
    execution.pop("_id", None)
    return execution


class EvidenceRepository:
    async def list_events(
        self,
        *,
        source: EventSource | None,
        severity: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        sources: tuple[EventSource, ...] = (source,) if source else ("instruction", "payment")
        query = {"severity": severity} if severity else {}
        documents: list[dict[str, Any]] = []
        per_source_limit = limit if source else min(limit, 500)
        for event_source in sources:
            collection = security_events_db()[event_collection_name(event_source)]
            async for document in (
                collection.find(query).sort("timestamp", -1).limit(per_source_limit)
            ):
                documents.append(serialize_event(document, event_source))
        documents.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return documents[:limit]

    async def get_event(
        self, source: EventSource, event_id: str
    ) -> dict[str, Any] | None:
        collection = security_events_db()[event_collection_name(source)]
        document = await collection.find_one({"_id": event_id})
        return serialize_event(document, source) if document else None

    async def list_executions(self, *, limit: int) -> list[dict[str, Any]]:
        collection = audit_db()[settings.audit_collection]
        documents = [
            serialize_execution(document)
            async for document in collection.find().sort("created_at", -1).limit(limit)
        ]
        return documents

    async def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        collection = audit_db()[settings.audit_collection]
        document = await collection.find_one({"_id": execution_id})
        return serialize_execution(document) if document else None

    async def get_opa_evidence(self, execution_id: str) -> dict[str, Any] | None:
        execution = await self.get_execution(execution_id)
        if execution is None:
            return None
        governance = execution.get("governance") or {}
        event_id = governance.get("security_event_id")
        if event_id:
            event = await self.get_event("payment", str(event_id))
            if event is None:
                return {
                    "source": "security_event",
                    "security_event_id": event_id,
                    "security_event": None,
                    "missing": True,
                }
            authorization = (event.get("details") or {}).get("authorization") or {}
            return {
                "source": "security_event",
                "security_event_id": event_id,
                "security_event": event,
                "evaluate_request": authorization.get("evaluate_request"),
                "evaluate_response": authorization.get("evaluate_response"),
                "authorization": authorization,
            }
        exchange = governance.get("policy_exchange")
        if exchange:
            return {
                "source": "policy_exchange",
                "security_event_id": None,
                "security_event": None,
                "evaluate_request": exchange.get("evaluate_request"),
                "evaluate_response": exchange.get("evaluate_response"),
                "authorization": None,
            }
        return {"source": "none", "security_event_id": None}
