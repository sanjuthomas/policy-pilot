from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from inst.security_event_ui_store import SecurityEventUiStore


@pytest.mark.asyncio
async def test_security_event_ui_store_connect() -> None:
    store = SecurityEventUiStore()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(
        return_value={"timestamp": datetime(2025, 6, 1, 12, 0, 0)}
    )

    with patch("inst.security_event_ui_store.get_security_events_database") as mock_get_db:
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

    with patch("inst.security_event_ui_store.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        event = await store.get_by_event_id("e1")

    assert event is not None
    assert event["event_id"] == "e1"


@pytest.mark.asyncio
async def test_security_event_ui_store_get_by_event_id_missing() -> None:
    store = SecurityEventUiStore()
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    with patch("inst.security_event_ui_store.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        assert await store.get_by_event_id("missing") is None
