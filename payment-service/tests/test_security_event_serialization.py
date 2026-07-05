from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from ps.security_event_serialization import (
    security_event_to_document,
    serialize_security_event,
)


def test_serialize_security_event_converts_object_id() -> None:
    oid = ObjectId()
    doc = {"_id": oid, "event_id": "evt-1"}
    result = serialize_security_event(doc)
    assert result["_id"] == str(oid)
    assert result["event_id"] == str(oid)


def test_serialize_security_event_exposes_event_id_from_document_id() -> None:
    doc = {"_id": "20260628-FICC-P-1-SE-1", "severity": "INFO"}
    result = serialize_security_event(doc)
    assert result["event_id"] == "20260628-FICC-P-1-SE-1"


def test_serialize_security_event_converts_datetime() -> None:
    ts = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
    doc = {"timestamp": ts, "nested": {"created": ts}}
    result = serialize_security_event(doc)
    assert result["timestamp"] == ts.isoformat()
    assert result["nested"]["created"] == ts.isoformat()


def test_serialize_security_event_preserves_primitives() -> None:
    doc = {"count": 3, "active": True, "label": "test", "items": [1, "two"]}
    result = serialize_security_event(doc)
    assert result == doc


def test_serialize_security_event_normalizes_nested_lists() -> None:
    oid = ObjectId()
    doc = {"items": [{"id": oid}, "plain"]}
    result = serialize_security_event(doc)
    assert result["items"][0]["id"] == str(oid)
    assert result["items"][1] == "plain"


def test_security_event_to_document_uses_sequence_id_as_id(
    subject,
    payment,
) -> None:
    from ps.models.enums import PaymentAction
    from ps.models.security_event import PaymentSecurityEvent

    event = PaymentSecurityEvent.authorized_action(
        PaymentAction.CREATE,
        subject,
        payment,
        version_number=1,
    )
    document = security_event_to_document(event, document_id="20260628-FICC-P-1-SE-1")
    assert document["_id"] == "20260628-FICC-P-1-SE-1"
    assert "event_id" not in document
