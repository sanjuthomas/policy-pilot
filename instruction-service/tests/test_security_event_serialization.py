from datetime import datetime

from bson import ObjectId

from inst.security_event_serialization import serialize_security_event


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
