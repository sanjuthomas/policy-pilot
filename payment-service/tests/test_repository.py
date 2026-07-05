from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ps.constants import PAYMENT_CURRENT_OUT
from ps.models.enums import PaymentAction, PaymentStatus, SecurityEventSeverity
from ps.models.payment import Payment
from ps.repository import (
    ConcurrentModificationError,
    PaymentNotFoundError,
    PaymentRepository,
)
from ps.security_event_repository import SecurityEventRepository
from ps.storage import VersionedPayment, versioned_payment_to_document
from pymongo.errors import DuplicateKeyError


@pytest.fixture
def mock_collection() -> MagicMock:
    col = MagicMock()
    col.insert_one = AsyncMock()
    col.find_one = AsyncMock()
    col.update_one = AsyncMock()
    col.create_index = AsyncMock()
    return col


@pytest.fixture
def patched_db(mock_collection: MagicMock):
    with patch("ps.repository.get_db", return_value={"payments": mock_collection}):
        yield mock_collection


def _versioned(payment: Payment, version: int = 1) -> VersionedPayment:
    return VersionedPayment(
        payment=payment,
        version_number=version,
        valid_in=payment.created_at.replace(tzinfo=None),
        valid_out=None,
    )


@pytest.mark.asyncio
async def test_insert_initial(patched_db: MagicMock, payment: Payment) -> None:
    repo = PaymentRepository()
    result = await repo.insert_initial(payment)
    patched_db.insert_one.assert_awaited_once()
    assert result.payment.payment_id == payment.payment_id
    assert result.version_number == 1


@pytest.mark.asyncio
async def test_insert_initial_passes_session(
    patched_db: MagicMock,
    payment: Payment,
) -> None:
    repo = PaymentRepository()
    session = MagicMock()
    await repo.insert_initial(payment, session=session)
    patched_db.insert_one.assert_awaited_once()
    assert patched_db.insert_one.call_args.kwargs["session"] is session


@pytest.mark.asyncio
async def test_append_version_success(
    patched_db: MagicMock,
    payment: Payment,
) -> None:
    current_doc = versioned_payment_to_document(
        payment,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    patched_db.find_one.return_value = current_doc
    patched_db.update_one.return_value = MagicMock(modified_count=1)

    repo = PaymentRepository()
    payment.status = PaymentStatus.SUBMITTED
    result = await repo.append_version(payment)

    patched_db.update_one.assert_awaited_once()
    patched_db.insert_one.assert_awaited_once()
    assert result.version_number == 2


@pytest.mark.asyncio
async def test_append_version_not_found(
    patched_db: MagicMock,
    payment: Payment,
) -> None:
    patched_db.find_one.return_value = None
    repo = PaymentRepository()
    with pytest.raises(PaymentNotFoundError):
        await repo.append_version(payment)


@pytest.mark.asyncio
async def test_append_version_concurrent_modification(
    patched_db: MagicMock,
    payment: Payment,
) -> None:
    current_doc = versioned_payment_to_document(
        payment,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    patched_db.find_one.return_value = current_doc
    patched_db.update_one.return_value = MagicMock(modified_count=0)

    repo = PaymentRepository()
    with pytest.raises(ConcurrentModificationError):
        await repo.append_version(payment)


@pytest.mark.asyncio
async def test_append_version_duplicate_key(
    patched_db: MagicMock,
    payment: Payment,
) -> None:
    current_doc = versioned_payment_to_document(
        payment,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    patched_db.find_one.return_value = current_doc
    patched_db.update_one.return_value = MagicMock(modified_count=1)
    patched_db.insert_one.side_effect = DuplicateKeyError("dup")

    repo = PaymentRepository()
    with pytest.raises(ConcurrentModificationError):
        await repo.append_version(payment)


@pytest.mark.asyncio
async def test_get_current(patched_db: MagicMock, payment: Payment) -> None:
    doc = versioned_payment_to_document(
        payment,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    patched_db.find_one.return_value = doc
    repo = PaymentRepository()
    record = await repo.get_current(payment.payment_id)
    assert record.payment.payment_id == payment.payment_id
    args, kwargs = patched_db.find_one.call_args
    assert args[0]["out"] == PAYMENT_CURRENT_OUT
    assert kwargs.get("session") is None


@pytest.mark.asyncio
async def test_list_current_excludes_cancelled(
    patched_db: MagicMock,
    payment: Payment,
) -> None:
    cancelled = payment.model_copy(deep=True)
    cancelled.status = PaymentStatus.CANCELLED
    cancelled_doc = versioned_payment_to_document(
        cancelled,
        version_number=2,
        valid_in=datetime.utcnow(),
    )
    active_doc = versioned_payment_to_document(
        payment,
        version_number=1,
        valid_in=datetime.utcnow(),
    )

    class AsyncCursor:
        def __init__(self, docs):
            self._docs = docs

        def sort(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def __aiter__(self):
            async def generator():
                for doc in self._docs:
                    yield doc

            return generator()

    patched_db.find = MagicMock(return_value=AsyncCursor([cancelled_doc, active_doc]))
    repo = PaymentRepository()
    records = await repo.list_current()
    assert len(records) == 1
    assert records[0].payment.status == PaymentStatus.DRAFT


@pytest.fixture
def event_collection() -> AsyncMock:
    col = AsyncMock()
    col.insert_one = AsyncMock()
    return col


@pytest.fixture
def event_repo(event_collection: AsyncMock):
    sequence_client = AsyncMock()
    sequence_client.next_security_event_id = AsyncMock(
        return_value="20260628-FICC-P-1-SE-1"
    )
    with patch(
        "ps.security_event_repository.get_security_events_db",
        return_value={"payment_service": event_collection},
    ):
        yield SecurityEventRepository(sequence_client=sequence_client), event_collection


@pytest.mark.asyncio
async def test_security_event_insert_document_passes_session(
    event_repo,
    payment: Payment,
) -> None:
    repo, col = event_repo
    session = MagicMock()
    document = {"_id": "evt-1"}
    await repo.insert_document(document, session=session)
    col.insert_one.assert_awaited_once_with(document, session=session)


@pytest.mark.asyncio
async def test_security_event_record_authorized_action(
    event_repo,
    subject,
    payment: Payment,
) -> None:
    repo, col = event_repo
    event = await repo.record_authorized_action(
        PaymentAction.CREATE,
        subject,
        payment,
        version_number=1,
        details={"authorization": {"summary": "ok"}},
    )
    col.insert_one.assert_awaited_once()
    assert event.event.action == "CREATE"
    stored = col.insert_one.call_args[0][0]
    assert stored["_id"] == "20260628-FICC-P-1-SE-1"
    assert "event_id" not in stored


@pytest.mark.asyncio
async def test_security_event_policy_denial(
    event_repo,
    subject,
    payment: Payment,
) -> None:
    repo, col = event_repo
    event = await repo.record_policy_denial(
        PaymentAction.APPROVE,
        subject,
        payment,
        reason="denied",
    )
    col.insert_one.assert_awaited_once()
    assert event.severity == SecurityEventSeverity.ALERT
