from datetime import datetime
from typing import Any

from bson import ObjectId

from ps.models.security_event import PaymentSecurityEvent


def security_event_to_document(
    event: PaymentSecurityEvent, *, document_id: str
) -> dict[str, Any]:
    """Serialize a security event for MongoDB; ``document_id`` becomes ``_id``."""
    document = event.model_dump(mode="json")
    document["_id"] = document_id
    return document


def serialize_security_event(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Mongo document for API/UI; exposes ``event_id`` from ``_id``."""
    result = _normalize(document)
    document_id = result.get("_id")
    if document_id is not None:
        result["event_id"] = str(document_id)
    return result


def _normalize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value
