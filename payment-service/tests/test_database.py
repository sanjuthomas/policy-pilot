from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ps.database import close, connect, get_db, get_security_events_db


@pytest.mark.asyncio
async def test_connect_and_close() -> None:
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.drop_index = AsyncMock()
    mock_collection.create_index = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    mock_client.close = MagicMock()

    with patch("ps.database._client", None):
        with patch("ps.database.AsyncIOMotorClient", return_value=mock_client):
            await connect()
            assert get_db() is mock_db
            mock_collection.drop_index.assert_any_await("payment_id_1")
            mock_collection.drop_index.assert_any_await("payment_id_version_unique")
            mock_collection.drop_index.assert_any_await("event_id_1")
            await close()
            mock_client.close.assert_called_once()


def test_get_security_events_db() -> None:
    mock_client = MagicMock()
    mock_events_db = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_events_db)
    with patch("ps.database._client", mock_client):
        assert get_security_events_db() is mock_events_db
