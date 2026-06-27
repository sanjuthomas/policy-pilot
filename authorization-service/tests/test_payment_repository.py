from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from authz.models import PaymentRecord, UserReference
from authz.payment_repository import PaymentNotFoundError, PaymentRepository


@pytest.mark.asyncio
async def test_get_payment_returns_record() -> None:
    repo = PaymentRepository()
    collection = MagicMock()
    collection.find_one = AsyncMock(
        return_value={
            "payment_id": "p1",
            "instruction_id": "i1",
            "instruction_version": 1,
            "status": "SUBMITTED",
            "amount": 100.0,
            "currency": "USD",
            "owning_lob": "FICC",
            "created_by": {"user_id": "pay-101", "supervisor_id": "pay-201"},
        }
    )
    repo._collection = collection

    payment = await repo.get_payment("p1")

    assert isinstance(payment, PaymentRecord)
    assert payment.payment_id == "p1"


@pytest.mark.asyncio
async def test_get_payment_not_found() -> None:
    repo = PaymentRepository()
    collection = MagicMock()
    collection.find_one = AsyncMock(return_value=None)
    repo._collection = collection

    with pytest.raises(PaymentNotFoundError):
        await repo.get_payment("missing")
