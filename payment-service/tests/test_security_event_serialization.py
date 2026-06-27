from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from ps.security_event_serialization import serialize_security_event


def test_serialize_security_event_converts_object_id() -> None:
    oid = ObjectId()
    doc = {"_id": oid, "event_id": "evt-1"}
    result = serialize_security_event(doc)
    assert result["_id"] == str(oid)
    assert result["event_id"] == "evt-1"


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
