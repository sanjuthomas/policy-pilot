from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pymongo.errors import ConnectionFailure
from seq.models import EntityType, NextSequenceRequest
from seq.repository import SequenceRepository, SequenceRepositoryError
from seq.service import SequenceService


@pytest.mark.asyncio
async def test_allocate_next_returns_incremented_value() -> None:
    collection = AsyncMock()
    collection.find_one_and_update = AsyncMock(return_value={"_id": "20260627-FICC-I", "seq": 2})

    with patch("seq.repository.get_db", return_value={"sequence_counters": collection}):
        repo = SequenceRepository()
        seq = await repo.allocate_next("20260627-FICC-I")

    assert seq == 2
    collection.find_one_and_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_allocate_next_wraps_mongo_errors() -> None:
    collection = AsyncMock()
    collection.find_one_and_update = AsyncMock(side_effect=ConnectionFailure("down"))

    with patch("seq.repository.get_db", return_value={"sequence_counters": collection}):
        repo = SequenceRepository()
        with pytest.raises(SequenceRepositoryError):
            await repo.allocate_next("20260627-FICC-I")


@pytest.mark.asyncio
async def test_allocate_next_rejects_missing_counter() -> None:
    collection = AsyncMock()
    collection.find_one_and_update = AsyncMock(return_value={"_id": "20260627-FICC-I"})

    with patch("seq.repository.get_db", return_value={"sequence_counters": collection}):
        repo = SequenceRepository()
        with pytest.raises(SequenceRepositoryError):
            await repo.allocate_next("20260627-FICC-I")


@pytest.mark.asyncio
async def test_service_builds_sequence_id(mock_repository: AsyncMock) -> None:
    mock_repository.allocate_next.return_value = 5
    service = SequenceService(mock_repository)

    response = await service.next_sequence(
        NextSequenceRequest(
            business_date=date(2026, 6, 27),
            owning_lob="FICC",
            entity_type=EntityType.INSTRUCTION,
        )
    )

    assert response.sequence_id == "20260627-FICC-I-5"
    assert response.sequence_number == 5
    assert response.counter_key == "20260627-FICC-I"
    mock_repository.allocate_next.assert_awaited_once_with("20260627-FICC-I")
