from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ilm.security_event_ui_store import SecurityEventUiStore


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


def test_main_health_endpoint() -> None:
    with patch("ilm.main.connect", AsyncMock()), \
         patch("ilm.main.close", AsyncMock()), \
         patch("ilm.main.kafka_publisher.start", AsyncMock()), \
         patch("ilm.main.kafka_publisher.close", AsyncMock()), \
         patch("ilm.main.security_event_ui_store.connect", AsyncMock()):

        from ilm.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "UP"
