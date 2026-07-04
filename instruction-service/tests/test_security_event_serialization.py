from datetime import datetime

from bson import ObjectId
from inst.security_event_serialization import (
    security_event_to_document,
    serialize_security_event,
)


def test_serialize_security_event_normalizes_object_id_and_datetime() -> None:
    oid = ObjectId()
    ts = datetime(2025, 6, 1, 12, 30, 45)
    document = {
        "_id": oid,
        "timestamp": ts,
        "nested": {
            "ids": [ObjectId(), "plain"],
            "when": ts,
        },
        "tags": ["a", "b"],
        "count": 42,
    }

    result = serialize_security_event(document)

    assert result["_id"] == str(oid)
    assert result["timestamp"] == ts.isoformat()
    assert isinstance(result["nested"]["ids"][0], str)
    assert result["nested"]["ids"][1] == "plain"
    assert result["nested"]["when"] == ts.isoformat()
    assert result["tags"] == ["a", "b"]
    assert result["count"] == 42


def test_serialize_security_event_exposes_event_id_from_document_id() -> None:
    document = {"_id": "20260628-FICC-I-1-SE-1", "severity": "INFO"}

    result = serialize_security_event(document)

    assert result["_id"] == "20260628-FICC-I-1-SE-1"
    assert result["event_id"] == "20260628-FICC-I-1-SE-1"


def test_security_event_to_document_uses_sequence_id_as_id(
    sample_subject,
    sample_instruction,
) -> None:
    from inst.models.enums import LifecycleAction
    from inst.models.security_event import SecurityEvent

    event = SecurityEvent.authorized_action(
        LifecycleAction.CREATE,
        sample_subject,
        sample_instruction,
        version_number=1,
    )
    document = security_event_to_document(event, document_id="20260628-FICC-I-1-SE-1")

    assert document["_id"] == "20260628-FICC-I-1-SE-1"
    assert "event_id" not in document
    assert document["severity"] == "INFO"
