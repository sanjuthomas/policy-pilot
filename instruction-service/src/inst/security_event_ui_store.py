from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection

from inst.config import settings
from inst.database import get_security_events_database
from inst.security_event_serialization import serialize_security_event

_NOTABLE_FILTER = {
    "$or": [
        {"severity": "ALERT"},
        {"event.outcome": "failure"},
    ]
}
_NOTABLE_EVENT_CAP = 100


class SecurityEventUiStore:
    @property
    def collection(self) -> AsyncIOMotorCollection:
        return get_security_events_database()[settings.security_events_collection]

    async def connect(self) -> None:
        return None

    async def list_recent(self, *, limit: int) -> list[dict[str, Any]]:
        notable_cap = min(limit, _NOTABLE_EVENT_CAP)
        notable_docs = [
            doc
            async for doc in self.collection.find(_NOTABLE_FILTER)
            .sort("timestamp", -1)
            .limit(notable_cap)
        ]
        info_docs = [
            doc
            async for doc in self.collection.find({"severity": "INFO"})
            .sort("timestamp", -1)
            .limit(limit)
        ]
        merged_docs = _merge_recent_documents(notable_docs, info_docs, limit=limit)
        return [serialize_security_event(doc) for doc in merged_docs]

    async def get_by_event_id(self, event_id: str) -> dict[str, Any] | None:
        document = await self.collection.find_one({"_id": event_id})
        if document is None:
            return None
        return serialize_security_event(document)


def _merge_recent_documents(
    notable_docs: list[dict[str, Any]],
    info_docs: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    notable_by_id: dict[str, dict[str, Any]] = {}
    for doc in notable_docs:
        document_id = _document_id(doc)
        if document_id and document_id not in notable_by_id:
            notable_by_id[document_id] = doc
    notable = sorted(notable_by_id.values(), key=_document_timestamp, reverse=True)[:limit]

    info_slots = max(0, limit - len(notable))
    if info_slots == 0:
        return notable

    info_candidates = [
        doc
        for doc in info_docs
        if _document_id(doc) and _document_id(doc) not in notable_by_id
    ]
    info = sorted(info_candidates, key=_document_timestamp, reverse=True)[:info_slots]
    return sorted(notable + info, key=_document_timestamp, reverse=True)


def _document_id(doc: dict[str, Any]) -> str | None:
    key = doc.get("_id")
    if key is not None:
        return str(key)
    legacy_id = doc.get("event_id")
    return str(legacy_id) if legacy_id is not None else None


def _document_timestamp(doc: dict[str, Any]) -> datetime:
    ts = doc.get("timestamp")
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None) if ts.tzinfo else ts
    if ts:
        return _parse_timestamp(str(ts))
    return datetime.min


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).replace(tzinfo=None)
