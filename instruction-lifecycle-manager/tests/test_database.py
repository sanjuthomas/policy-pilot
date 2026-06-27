from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ilm.config import Settings
from ilm.database import (
    close,
    connect,
    get_client,
    get_database,
    get_security_events_database,
)


@pytest.mark.asyncio
async def test_connect_and_close(monkeypatch) -> None:
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    mock_db.instructions = mock_collection
    mock_client.__getitem__ = MagicMock(return_value=mock_db)
    mock_client.close = MagicMock()

    with patch("ilm.database._client", None):
        with patch("ilm.database.AsyncIOMotorClient", return_value=mock_client):
            await connect()
            assert get_client() is mock_client
            assert get_database() is mock_db
            await close()
            mock_client.close.assert_called_once()


def test_get_security_events_database(monkeypatch) -> None:
    mock_client = MagicMock()
    mock_events_db = MagicMock()
    mock_client.__getitem__ = MagicMock(return_value=mock_events_db)
    with patch("ilm.database._client", mock_client):
        assert get_security_events_database() is mock_events_db


def test_settings_loads_pat_from_file(tmp_path: Path) -> None:
    pat_file = tmp_path / "pat.txt"
    pat_file.write_text("secret-pat\n", encoding="utf-8")
    settings = Settings(
        zitadel_service_pat_file=pat_file,
        zitadel_service_pat=None,
    )
    assert settings.zitadel_service_pat == "secret-pat"
