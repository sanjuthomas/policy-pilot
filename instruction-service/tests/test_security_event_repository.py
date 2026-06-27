from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ilm.models.enums import LifecycleAction
from ilm.models.security_event import SecurityEvent
from ilm.security_event_repository import SecurityEventRepository


@pytest.fixture
def mock_collection() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_collection: MagicMock) -> SecurityEventRepository:
    with patch("ilm.security_event_repository.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        yield SecurityEventRepository(collection_name="test-events")


@pytest.mark.asyncio
async def test_insert_document(repo: SecurityEventRepository, mock_collection: MagicMock) -> None:
    mock_collection.insert_one = AsyncMock()
    doc = {"event_id": "e1"}
    result = await repo.insert_document(doc)
    assert result == doc
    mock_collection.insert_one.assert_awaited_once_with(doc, session=None)


@pytest.mark.asyncio
async def test_publish_delegates_to_kafka(
    repo: SecurityEventRepository,
) -> None:
    with patch("ilm.security_event_repository.kafka_publisher") as mock_kafka:
        mock_kafka.publish = AsyncMock()
        await repo.publish({"event_id": "e1"})
        mock_kafka.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_replace_document(repo: SecurityEventRepository, mock_collection: MagicMock) -> None:
    mock_collection.replace_one = AsyncMock()
    with patch("ilm.security_event_repository.kafka_publisher") as mock_kafka:
        mock_kafka.publish = AsyncMock()
        await repo.replace_document({"event_id": "e1", "_id": "oid"})
        mock_collection.replace_one.assert_awaited_once()
        mock_kafka.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_replace_document_missing_event_id(repo: SecurityEventRepository) -> None:
    with pytest.raises(ValueError, match="event_id"):
        await repo.replace_document({})


@pytest.mark.asyncio
async def test_find_missing_authorization(
    repo: SecurityEventRepository,
    mock_collection: MagicMock,
) -> None:
    async def _async_iter():
        yield {"event_id": "e1"}

    mock_collection.find.return_value = _async_iter()
    docs = await repo.find_missing_authorization(limit=10)
    assert docs == [{"event_id": "e1"}]


@pytest.mark.asyncio
async def test_insert_and_record_methods(
    sample_subject,
    sample_instruction,
) -> None:
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()
    with patch("ilm.security_event_repository.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        repo = SecurityEventRepository(collection_name="test-events")
        with patch("ilm.security_event_repository.kafka_publisher") as mock_kafka:
            mock_kafka.publish = AsyncMock()
            event = await repo.record_authorized_action(
                LifecycleAction.CREATE,
                sample_subject,
                sample_instruction,
                version_number=1,
            )
    assert isinstance(event, SecurityEvent)
    assert event.event.action == "CREATE"
