import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from ilm.security_event_broadcaster import SecurityEventBroadcaster
from ilm.security_event_ui_store import SecurityEventUiStore
from ilm.ui_broadcaster import InstructionBroadcaster
from ilm.ui_watcher import (
    InstructionWatcher,
    _format_timestamp,
    instruction_from_document,
)


@pytest.mark.asyncio
async def test_instruction_broadcaster_publish_and_sse() -> None:
    broadcaster = InstructionBroadcaster()
    payload = {"instruction_id": "i1", "version_number": 1}
    sse = InstructionBroadcaster.sse_payload(payload)
    assert sse.startswith("data: ")
    assert "i1" in sse

    async def consume_one():
        gen = broadcaster.subscribe()
        task = asyncio.create_task(gen.__anext__())
        await asyncio.sleep(0)
        await broadcaster.publish(payload)
        result = await asyncio.wait_for(task, timeout=1)
        await gen.aclose()
        return result

    received = await consume_one()
    assert received == payload


@pytest.mark.asyncio
async def test_security_event_broadcaster_sse_payload() -> None:
    payload = {"event_id": "e1"}
    sse = SecurityEventBroadcaster.sse_payload(payload)
    parsed = json.loads(sse.removeprefix("data: ").strip())
    assert parsed["event_id"] == "e1"


@pytest.mark.asyncio
async def test_security_event_ui_store_list_recent() -> None:
    store = SecurityEventUiStore()
    mock_collection = MagicMock()

    async def _async_iter():
        yield {
            "event_id": "e1",
            "timestamp": "2025-01-01T00:00:00Z",
        }

    mock_collection.find.return_value.sort.return_value.limit.return_value = _async_iter()

    with patch("ilm.security_event_ui_store.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        events = await store.list_recent(limit=5)
    assert events[0]["event_id"] == "e1"
    assert "e1" in store.seen_event_ids


def test_security_event_ui_store_remember_helpers() -> None:
    store = SecurityEventUiStore()
    assert store.remember_event_id("e1") is True
    assert store.remember_event_id("e1") is False
    store.remember_poll_timestamp("2025-06-01T00:00:00Z")
    assert store.last_poll_at is not None


def test_instruction_from_document(sample_instruction) -> None:
    from datetime import datetime

    from ilm.storage import versioned_instruction_to_document

    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    result = instruction_from_document(doc)
    assert result["instruction_id"] == sample_instruction.instruction_id
    assert result["version_number"] == 1


def test_format_timestamp() -> None:
    from datetime import datetime

    assert _format_timestamp(datetime(2025, 1, 1, 0, 0, 0)) == "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_instruction_watcher_connect() -> None:
    watcher = InstructionWatcher()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value={"in": "2025-01-01T00:00:00Z"})
    with patch("ilm.ui_watcher.get_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        await watcher.connect()
    assert watcher._last_poll_at is not None


def test_main_health_endpoint() -> None:
    with patch("ilm.main.connect", AsyncMock()), \
         patch("ilm.main.close", AsyncMock()), \
         patch("ilm.main.kafka_publisher.start", AsyncMock()), \
         patch("ilm.main.kafka_publisher.close", AsyncMock()), \
         patch("ilm.main.security_event_ui_store.connect", AsyncMock()), \
         patch("ilm.main.InstructionWatcher") as mock_instr_watcher, \
         patch("ilm.main.SecurityEventWatcher") as mock_sec_watcher:

        mock_instr = MagicMock()
        mock_instr.connect = AsyncMock()
        mock_instr.watch = AsyncMock(side_effect=asyncio.CancelledError())
        mock_instr_watcher.return_value = mock_instr

        mock_sec = MagicMock()
        mock_sec.connect = AsyncMock()
        mock_sec.watch = AsyncMock(side_effect=asyncio.CancelledError())
        mock_sec_watcher.return_value = mock_sec

        from ilm.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "UP"
