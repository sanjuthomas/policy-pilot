from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from authz.models import PaymentRecord, Subject, UserReference
from authz.opa import OpaClient


@pytest.mark.asyncio
async def test_can_approve_payment_returns_basis() -> None:
    client = OpaClient(base_url="http://opa.test")
    payment = PaymentRecord(
        payment_id="p1",
        instruction_id="i1",
        instruction_version=1,
        status="SUBMITTED",
        amount=100.0,
        currency="USD",
        owning_lob="FICC",
        created_by=UserReference(user_id="pay-101"),
    )
    subject = Subject(user_id="pay-201", title="VP", roles=["FUNDING_APPROVER"])

    with patch.object(client, "_post_data", new_callable=AsyncMock) as post_data:
        post_data.side_effect = [True, ["has_role", "covers_lob"]]
        allowed, basis = await client.can_approve_payment(
            subject,
            payment,
            instruction_end_date="2027-01-01",
            instruction_status="APPROVED",
        )

    assert allowed is True
    assert basis == ["has_role", "covers_lob"]


@pytest.mark.asyncio
async def test_can_approve_payment_denied() -> None:
    client = OpaClient(base_url="http://opa.test")
    payment = PaymentRecord(
        payment_id="p1",
        instruction_id="i1",
        instruction_version=1,
        status="SUBMITTED",
        amount=100.0,
        currency="USD",
        owning_lob="FICC",
        created_by=UserReference(user_id="pay-101"),
    )
    subject = Subject(user_id="pay-202", title="VP", roles=["FUNDING_APPROVER"])

    with patch.object(client, "_post_data", new_callable=AsyncMock, return_value=False):
        allowed, basis = await client.can_approve_payment(
            subject,
            payment,
            instruction_end_date="2027-01-01",
            instruction_status="APPROVED",
        )

    assert allowed is False
    assert basis == []


@pytest.mark.asyncio
async def test_can_approve_instruction_returns_basis() -> None:
    client = OpaClient(base_url="http://opa.test")
    subject = Subject(user_id="ficc-300", title="Vice President", roles=["INSTRUCTION_APPROVER"], lob="FICC")
    opa_instruction = {
        "status": "SUBMITTED",
        "type": "STANDING",
        "owning_lob": "FICC",
        "effective_date": "2026-01-01T00:00:00Z",
        "end_date": "2027-01-01T00:00:00Z",
        "created_by": {"user_id": "ficc-101", "title": "Analyst", "supervisor_id": "ficc-201"},
        "suspended_by": None,
    }
    opa_account = {"owning_lob": "FICC"}

    with patch.object(client, "_post_data", new_callable=AsyncMock) as post_data:
        post_data.side_effect = [True, ["approval matrix"]]
        allowed, basis = await client.can_approve_instruction(
            subject,
            opa_instruction=opa_instruction,
            opa_account=opa_account,
        )

    assert allowed is True
    assert basis == ["approval matrix"]
