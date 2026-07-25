from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from audit_console.repository import (
    EvidenceRepository,
    event_collection_name,
    normalize,
    serialize_event,
    serialize_execution,
)


class AsyncCursor:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def sort(self, *_args):
        return self

    def limit(self, limit: int):
        self.documents = self.documents[:limit]
        return self

    def __aiter__(self):
        async def generate():
            for document in self.documents:
                yield document

        return generate()


def test_serializers_and_collection_names() -> None:
    object_id = ObjectId()
    normalized = normalize(
        {"id": object_id, "at": datetime(2026, 1, 1), "nested": [object_id]}
    )
    assert normalized["id"] == str(object_id)
    assert normalized["at"].endswith("Z")
    assert event_collection_name("instruction") == "instruction_service"
    assert event_collection_name("payment") == "payment_service"
    assert serialize_event({"_id": "E-1"}, "payment")["domain"] == "payment"
    execution = serialize_execution({"_id": "AUD-1"})
    assert execution == {"execution_id": "AUD-1"}


@pytest.mark.asyncio
async def test_event_list_and_get() -> None:
    instruction = MagicMock()
    payment = MagicMock()
    instruction.find.return_value = AsyncCursor(
        [{"_id": "I-SE-1", "timestamp": "2026-07-24T10:00:00Z", "severity": "INFO"}]
    )
    payment.find.return_value = AsyncCursor(
        [{"_id": "P-SE-1", "timestamp": "2026-07-24T11:00:00Z", "severity": "ALERT"}]
    )
    payment.find_one = AsyncMock(return_value={"_id": "P-SE-1", "severity": "ALERT"})
    database = {
        "instruction_service": instruction,
        "payment_service": payment,
    }
    repo = EvidenceRepository()
    with patch("audit_console.repository.security_events_db", return_value=database):
        events = await repo.list_events(source=None, severity=None, limit=10)
        event = await repo.get_event("payment", "P-SE-1")

    assert [item["event_id"] for item in events] == ["P-SE-1", "I-SE-1"]
    assert event and event["domain"] == "payment"


@pytest.mark.asyncio
async def test_audit_list_get_and_opa_sources() -> None:
    collection = MagicMock()
    collection.find.return_value = AsyncCursor(
        [{"_id": "AUD-1", "created_at": "2026-07-24T11:00:00Z"}]
    )
    collection.find_one = AsyncMock(
        side_effect=[
            {"_id": "AUD-1"},
            {
                "_id": "AUD-1",
                "governance": {"security_event_id": "P-SE-1"},
            },
            {
                "_id": "AUD-2",
                "governance": {
                    "policy_exchange": {
                        "evaluate_request": {"action": "CREATE"},
                        "evaluate_response": {"allowed": False},
                    }
                },
            },
        ]
    )
    audit_database = {"audit_executions": collection}
    repo = EvidenceRepository()

    with patch("audit_console.repository.audit_db", return_value=audit_database):
        executions = await repo.list_executions(limit=10)
        execution = await repo.get_execution("AUD-1")
        with patch.object(
            repo,
            "get_event",
            AsyncMock(
                return_value={
                    "event_id": "P-SE-1",
                    "details": {
                        "authorization": {
                            "evaluate_request": {"action": "CREATE"},
                            "evaluate_response": {"allowed": True},
                        }
                    },
                }
            ),
        ):
            linked = await repo.get_opa_evidence("AUD-1")
        preflight = await repo.get_opa_evidence("AUD-2")

    assert executions[0]["execution_id"] == "AUD-1"
    assert execution and execution["execution_id"] == "AUD-1"
    assert linked and linked["source"] == "security_event"
    assert linked["evaluate_response"]["allowed"] is True
    assert preflight and preflight["source"] == "policy_exchange"
