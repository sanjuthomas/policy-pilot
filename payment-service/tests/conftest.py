from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from ps.models.api import Subject
from ps.models.enums import PaymentStatus
from ps.models.payment import Payment


@pytest.fixture
def subject() -> Subject:
    return Subject(
        user_id="alice",
        given_name="Alice",
        family_name="Smith",
        title="VP Finance",
        lob="CORP",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        supervisor_id="boss1",
        covering_lobs=["CORP", "RETAIL"],
    )


@pytest.fixture
def approver_subject() -> Subject:
    return Subject(
        user_id="bob",
        given_name="Bob",
        family_name="Jones",
        title="Managing Director",
        lob="CORP",
        roles=["FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE"],
        supervisor_id=None,
        covering_lobs=["CORP"],
    )


@pytest.fixture
def payment(subject: Subject) -> Payment:
    return Payment.create(
        instruction_id="instr-001",
        instruction_version=1,
        amount=1_000_000.0,
        currency="USD",
        value_date="2026-07-01",
        owning_lob="CORP",
        instruction_type="STANDING",
        subject=subject,
        event_id="evt-create-001",
    )


@pytest.fixture
def submitted_payment(payment: Payment, subject: Subject) -> Payment:
    payment.status = PaymentStatus.SUBMITTED
    payment.submitted_by = payment.created_by
    return payment


@pytest.fixture
def standing_instruction() -> dict:
    future = datetime.now(timezone.utc) + timedelta(days=30)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    return {
        "instruction_id": "instr-001",
        "status": "STANDING",
        "version_number": 1,
        "currency": "USD",
        "owning_lob": "CORP",
        "end_date": future.isoformat(),
        "effective_date": past.isoformat(),
        "instruction_type": "STANDING",
    }
