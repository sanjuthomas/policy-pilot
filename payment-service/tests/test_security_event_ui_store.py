from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ps.security_event_ui_store import (
    SecurityEventUiStore,
    _document_id,
    _document_timestamp,
    _merge_recent_documents,
    _parse_timestamp,
)


def test_parse_timestamp_z_suffix() -> None:
    parsed = _parse_timestamp("2025-06-01T12:00:00Z")
    assert parsed == datetime(2025, 6, 1, 12, 0, 0)


def test_document_id_prefers_mongo_id() -> None:
    assert _document_id({"_id": "e1", "event_id": "legacy"}) == "e1"
    assert _document_id({"event_id": "legacy"}) == "legacy"
    assert _document_id({}) is None


def test_document_timestamp_from_datetime() -> None:
    ts = datetime(2025, 1, 2, 3, 4, 5)
    assert _document_timestamp({"timestamp": ts}) == ts


def test_merge_recent_documents_prioritizes_notable() -> None:
    notable = [{"_id": "a", "timestamp": "2025-06-02T00:00:00Z", "severity": "ALERT"}]
    info = [{"_id": "b", "timestamp": "2025-06-01T00:00:00Z", "severity": "INFO"}]
    merged = _merge_recent_documents(notable, info, limit=2)
    assert len(merged) == 2
    assert merged[0]["_id"] == "a"


def test_merge_recent_documents_notable_only_when_limit_reached() -> None:
    notable = [
        {"_id": "a", "timestamp": "2025-06-02T00:00:00Z"},
        {"_id": "b", "timestamp": "2025-06-01T00:00:00Z"},
    ]
    merged = _merge_recent_documents(notable, [], limit=1)
    assert len(merged) == 1


@pytest.mark.asyncio
async def test_security_event_ui_store_connect() -> None:
    store = SecurityEventUiStore()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(
        return_value={"timestamp": datetime(2025, 6, 1, 12, 0, 0)}
    )

    with patch("ps.security_event_ui_store.get_security_events_db") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        await store.connect()

    assert store.last_poll_at is not None


@pytest.mark.asyncio
async def test_security_event_ui_store_get_by_event_id() -> None:
    store = SecurityEventUiStore()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(
        return_value={"_id": "e1", "severity": "INFO", "timestamp": "2025-01-01T00:00:00Z"}
    )

    with patch("ps.security_event_ui_store.get_security_events_db") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        event = await store.get_by_event_id("e1")

    assert event is not None
    assert event["event_id"] == "e1"


@pytest.mark.asyncio
async def test_security_event_ui_store_remember_helpers() -> None:
    store = SecurityEventUiStore()
    assert store.remember_event_id("e1") is True
    assert store.remember_event_id("e1") is False
    store.remember_poll_timestamp("2025-06-01T00:00:00Z")
    assert store.last_poll_at == datetime(2025, 6, 1, 0, 0, 0)
