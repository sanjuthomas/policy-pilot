from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from inst.models.enums import LifecycleAction
from inst.models.security_event import SecurityEvent
from inst.security_event_repository import SecurityEventRepository


@pytest.fixture
def mock_collection() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_collection: MagicMock) -> SecurityEventRepository:
    sequence_client = AsyncMock()
    sequence_client.next_security_event_id = AsyncMock(
        return_value="20260628-FICC-I-1-SE-1"
    )
    with patch("inst.security_event_repository.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        yield SecurityEventRepository(
            collection_name="test-events",
            sequence_client=sequence_client,
        )


@pytest.mark.asyncio
async def test_insert_document(repo: SecurityEventRepository, mock_collection: MagicMock) -> None:
    mock_collection.insert_one = AsyncMock()
    doc = {"_id": "e1"}
    result = await repo.insert_document(doc)
    assert result == doc
    mock_collection.insert_one.assert_awaited_once_with(doc, session=None)


@pytest.mark.asyncio
async def test_insert_and_record_methods(
    sample_subject,
    sample_instruction,
) -> None:
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()
    sequence_client = AsyncMock()
    sequence_client.next_security_event_id = AsyncMock(
        return_value="20260628-FICC-I-1-SE-1"
    )
    with patch("inst.security_event_repository.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        repo = SecurityEventRepository(
            collection_name="test-events",
            sequence_client=sequence_client,
        )
        event = await repo.record_authorized_action(
            LifecycleAction.CREATE,
            sample_subject,
            sample_instruction,
            version_number=1,
        )
    assert isinstance(event, SecurityEvent)
    assert event.event.action == "CREATE"
    mock_collection.insert_one.assert_awaited_once()
    stored = mock_collection.insert_one.call_args[0][0]
    assert stored["_id"] == "20260628-FICC-I-1-SE-1"
    assert "event_id" not in stored


@pytest.mark.asyncio
async def test_insert(
    repo: SecurityEventRepository,
    mock_collection: MagicMock,
    sample_subject,
    sample_instruction,
) -> None:
    mock_collection.insert_one = AsyncMock()
    from inst.models.security_event import SecurityEvent

    event = SecurityEvent.authorized_action(
        LifecycleAction.CREATE,
        sample_subject,
        sample_instruction,
        version_number=1,
    )
    result = await repo.insert(event)
    assert isinstance(result, SecurityEvent)
    mock_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_policy_denial(
    sample_subject,
    sample_instruction,
) -> None:
    mock_collection = MagicMock()
    mock_collection.insert_one = AsyncMock()
    sequence_client = AsyncMock()
    sequence_client.next_security_event_id = AsyncMock(
        return_value="20260628-FICC-I-1-SE-2"
    )
    with patch("inst.security_event_repository.get_security_events_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        repo = SecurityEventRepository(
            collection_name="test-events",
            sequence_client=sequence_client,
        )
        event = await repo.record_policy_denial(
            LifecycleAction.APPROVE,
            sample_subject,
            sample_instruction,
            reason="denied",
            version_number=2,
        )
    assert event.severity.value == "ALERT"
    assert event.resource.version_number == 2
    stored = mock_collection.insert_one.call_args[0][0]
    assert stored["_id"] == "20260628-FICC-I-1-SE-2"
    assert stored["resource"]["version_number"] == 2
    assert stored["resource"]["id"] == sample_instruction.instruction_id

@pytest.mark.asyncio
async def test_allocate_event_id_failure(repo: SecurityEventRepository) -> None:
    from sequence_client.errors import SequenceClientError

    repo.sequence.next_security_event_id = AsyncMock(
        side_effect=SequenceClientError("down")
    )
    with pytest.raises(RuntimeError, match="security event sequence allocation failed"):
        await repo.allocate_event_id("instr-001")
