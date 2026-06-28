from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def disable_open_telemetry_for_tests() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"


@pytest.fixture
def mock_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.connect = AsyncMock()
    repo.close = AsyncMock()
    repo.ensure_indexes = AsyncMock()
    repo.allocate_next = AsyncMock(return_value=1)
    return repo


@pytest.fixture
def test_client(mock_repository: AsyncMock):
    with patch("seq.main.SequenceRepository", return_value=mock_repository):
        from seq import main as main_module
        from seq.service import SequenceService

        main_module.sequence_repository = mock_repository
        main_module.sequence_service = SequenceService(mock_repository)

        with TestClient(main_module.app) as client:
            yield client, mock_repository

        main_module.sequence_repository = None
        main_module.sequence_service = None
