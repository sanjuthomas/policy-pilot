"""End-to-end payment + instruction lifecycle scenarios (in-memory service wiring).

These tests drive PaymentService through multi-step flows with a stateful mock
instruction store so we can verify SINGLE_USE vs STANDING behavior without
Docker or external services.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ps.authorization import PolicyDecision
from ps.instruction_client import InstructionNotFoundError, InstructionStateError
from ps.models.api import CancelPaymentRequest, Subject
from ps.models.enums import PaymentStatus
from ps.repository import PaymentNotFoundError
from ps.service import InvalidStateTransitionError, PaymentService
from ps.storage import VersionedPayment


def _allow_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        allow_basis=["policy ok"],
        violations=[],
        is_alert=False,
    )


class InstructionState:
    """Minimal instruction record whose status transitions like instruction-service."""

    def __init__(
        self,
        *,
        instruction_id: str,
        instruction_type: str,
        owning_lob: str = "CORP",
    ) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=30)
        past = datetime.now(timezone.utc) - timedelta(days=1)
        self.instruction_id = instruction_id
        self.instruction_type = instruction_type
        self.status = "DRAFT"
        self.version_number = 1
        self.currency = "USD"
        self.owning_lob = owning_lob
        self.end_date = future.isoformat()
        self.effective_date = past.isoformat()
        self.used_by: str | None = None

    def as_dict(self) -> dict:
        return {
            "instruction_id": self.instruction_id,
            "instruction_type": self.instruction_type,
            "status": self.status,
            "version_number": self.version_number,
            "currency": self.currency,
            "owning_lob": self.owning_lob,
            "end_date": self.end_date,
            "effective_date": self.effective_date,
            "used_by": self.used_by,
        }

    def submit_for_approval(self) -> None:
        if self.status != "DRAFT":
            raise InvalidInstructionTransition(
                f"instruction must be DRAFT to submit (status={self.status})"
            )
        self.status = "SUBMITTED"
        self.version_number += 1

    def approve(self) -> None:
        if self.status != "SUBMITTED":
            raise InvalidInstructionTransition(
                f"instruction must be SUBMITTED to approve (status={self.status})"
            )
        self.status = "APPROVED"
        self.version_number += 1

    def mark_used_for_payment(self, payment_id: str) -> None:
        if self.status != "APPROVED":
            raise InstructionStateError(
                f"instruction {self.instruction_id} cannot be marked USED: "
                f"status is {self.status}, expected APPROVED"
            )
        if self.instruction_type == "SINGLE_USE":
            self.status = "USED"
            self.used_by = payment_id
            self.version_number += 1

    def release_use_for_payment(self, payment_id: str) -> None:
        if self.status != "USED":
            raise InstructionStateError(
                f"instruction {self.instruction_id} cannot be released: status is {self.status}"
            )
        if self.used_by != payment_id:
            raise InstructionStateError("instruction used_by does not match the releasing payment")
        self.status = "APPROVED"
        self.used_by = None
        self.version_number += 1


class InvalidInstructionTransition(Exception):
    pass


class InMemoryPaymentRepo:
    def __init__(self) -> None:
        self._records: dict[str, VersionedPayment] = {}

    async def insert_initial(self, payment, session=None) -> VersionedPayment:
        record = VersionedPayment(
            payment=payment.model_copy(deep=True),
            version_number=1,
            valid_in=payment.created_at.replace(tzinfo=None),
            valid_out=None,
        )
        self._records[payment.payment_id] = record
        return deepcopy(record)

    async def append_version(self, payment, session=None) -> VersionedPayment:
        current = self._records[payment.payment_id]
        record = VersionedPayment(
            payment=payment.model_copy(deep=True),
            version_number=current.version_number + 1,
            valid_in=payment.updated_at.replace(tzinfo=None),
            valid_out=None,
        )
        self._records[payment.payment_id] = record
        return deepcopy(record)

    async def get_current(self, payment_id: str) -> VersionedPayment:
        try:
            return deepcopy(self._records[payment_id])
        except KeyError as exc:
            raise PaymentNotFoundError(payment_id) from exc

    async def list_current(
        self,
        *,
        instruction_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        include_cancelled: bool = False,
    ) -> list[VersionedPayment]:
        records = list(self._records.values())
        if instruction_id:
            records = [
                record
                for record in records
                if record.payment.instruction_id == instruction_id
            ]
        if status:
            records = [
                record for record in records if record.payment.status.value == status
            ]
        if not include_cancelled:
            records = [
                record
                for record in records
                if record.payment.status != PaymentStatus.CANCELLED
            ]
        records = records[:limit]
        return [deepcopy(record) for record in records]

    def payment_status(self, payment_id: str) -> PaymentStatus:
        return self._records[payment_id].payment.status


@pytest.fixture
def creator_subject() -> Subject:
    return Subject(
        user_id="mo-creator",
        given_name="Morgan",
        family_name="Lee",
        title="Middle Office Analyst",
        lob="MO",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        supervisor_id="mo-boss",
        covering_lobs=["CORP"],
    )


@pytest.fixture
def submit_subject() -> Subject:
    return Subject(
        user_id="fo-desk",
        given_name="Alex",
        family_name="Morrison",
        title="Front Office Analyst",
        lob="CORP",
        roles=["PAYMENT_CREATOR"],
        groups=[],
        supervisor_id="fo-boss",
        covering_lobs=[],
    )


@pytest.fixture
def approver_subject() -> Subject:
    return Subject(
        user_id="funding-approver",
        given_name="Bob",
        family_name="Jones",
        title="Managing Director",
        lob="MO",
        roles=["FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE"],
        supervisor_id=None,
        covering_lobs=["CORP"],
    )


def _build_scenario_service(instruction: InstructionState) -> PaymentService:
    repo = InMemoryPaymentRepo()
    payment_ids = iter(["20260704-CORP-P-1", "20260704-CORP-P-2"])

    service = PaymentService(sequence_client=AsyncMock())
    service.sequence.next_payment_id = AsyncMock(
        side_effect=lambda **_: next(payment_ids)
    )
    service.repo = repo
    service.event_repo = AsyncMock()
    service.event_repo.allocate_event_id = AsyncMock(
        side_effect=lambda payment_id: f"{payment_id}-SE-1"
    )
    service.event_repo.insert_document = AsyncMock(return_value={})
    service.authz = AsyncMock()
    service.authz.evaluate_payment = AsyncMock(return_value=_allow_decision())

    async def get_instruction(instruction_id: str, **_) -> dict:
        if instruction_id != instruction.instruction_id:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        return instruction.as_dict()

    async def mark_used(instruction_id: str, payment_id: str, **_) -> dict:
        if instruction_id != instruction.instruction_id:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        instruction.mark_used_for_payment(payment_id)
        return instruction.as_dict()

    async def release_use(instruction_id: str, payment_id: str, **_) -> dict:
        if instruction_id != instruction.instruction_id:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        instruction.release_use_for_payment(payment_id)
        return instruction.as_dict()

    service.instruction_service = AsyncMock()
    service.instruction_service.get_instruction = AsyncMock(side_effect=get_instruction)
    service.instruction_service.mark_used = AsyncMock(side_effect=mark_used)
    service.instruction_service.release_use = AsyncMock(side_effect=release_use)

    service._repo = repo  # expose for assertions
    service._instruction = instruction
    return service


@contextmanager
def _patched_txn():
    with patch("ps.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_tx


async def _create_two_draft_payments(
    service: PaymentService,
    creator: Subject,
    instruction_id: str,
) -> tuple[str, str]:
    with _patched_txn():
        first = await service.create(
            instruction_id=instruction_id,
            value_date="2026-07-05",
            amount=1_000_000.0,
            subject=creator,
        )
        second = await service.create(
            instruction_id=instruction_id,
            value_date="2026-07-05",
            amount=2_000_000.0,
            subject=creator,
        )
    return first.payment.payment_id, second.payment.payment_id


async def _expect_submit_rejected(
    service: PaymentService,
    submitter: Subject,
    payment_id: str,
) -> None:
    with _patched_txn(), pytest.raises(ValueError, match="must be APPROVED"):
        await service.submit(payment_id, submitter)


async def _submit_payment(
    service: PaymentService,
    submitter: Subject,
    payment_id: str,
) -> None:
    with _patched_txn():
        await service.submit(payment_id, submitter)


@pytest.mark.asyncio
async def test_single_use_instruction_payment_lifecycle(
    creator_subject: Subject,
    submit_subject: Subject,
    approver_subject: Subject,
) -> None:
    instruction = InstructionState(
        instruction_id="instr-single-use-1",
        instruction_type="SINGLE_USE",
    )
    service = _build_scenario_service(instruction)
    repo = service._repo

    payment_one_id, payment_two_id = await _create_two_draft_payments(
        service,
        creator_subject,
        instruction.instruction_id,
    )
    assert repo.payment_status(payment_one_id) == PaymentStatus.DRAFT
    assert repo.payment_status(payment_two_id) == PaymentStatus.DRAFT
    assert instruction.status == "DRAFT"

    await _expect_submit_rejected(service, submit_subject, payment_one_id)
    await _expect_submit_rejected(service, submit_subject, payment_two_id)

    instruction.submit_for_approval()
    assert instruction.status == "SUBMITTED"

    await _expect_submit_rejected(service, submit_subject, payment_one_id)
    await _expect_submit_rejected(service, submit_subject, payment_two_id)

    instruction.approve()
    assert instruction.status == "APPROVED"

    with _patched_txn(), pytest.raises(ValueError, match="SINGLE_USE"):
        await service.submit(payment_one_id, submit_subject)
    with _patched_txn(), pytest.raises(ValueError, match="SINGLE_USE"):
        await service.submit(payment_two_id, submit_subject)

    with _patched_txn():
        await service.cancel(
            payment_two_id,
            creator_subject,
            CancelPaymentRequest(reason="withdraw duplicate draft"),
        )
    assert repo.payment_status(payment_two_id) == PaymentStatus.CANCELLED

    await _submit_payment(service, submit_subject, payment_one_id)
    assert repo.payment_status(payment_one_id) == PaymentStatus.SUBMITTED
    assert instruction.status == "USED"
    assert instruction.used_by == payment_one_id
    service.instruction_service.mark_used.assert_awaited_once()

    with _patched_txn(), pytest.raises(InvalidStateTransitionError, match="only DRAFT"):
        await service.submit(payment_two_id, submit_subject)

    with _patched_txn():
        approved = await service.approve(payment_one_id, approver_subject)
    assert approved.payment.status == PaymentStatus.APPROVED


@pytest.mark.asyncio
async def test_standing_instruction_payment_lifecycle(
    creator_subject: Subject,
    submit_subject: Subject,
    approver_subject: Subject,
) -> None:
    instruction = InstructionState(
        instruction_id="instr-standing-1",
        instruction_type="STANDING",
    )
    service = _build_scenario_service(instruction)
    repo = service._repo

    payment_one_id, payment_two_id = await _create_two_draft_payments(
        service,
        creator_subject,
        instruction.instruction_id,
    )

    await _expect_submit_rejected(service, submit_subject, payment_one_id)
    await _expect_submit_rejected(service, submit_subject, payment_two_id)

    instruction.submit_for_approval()
    await _expect_submit_rejected(service, submit_subject, payment_one_id)
    await _expect_submit_rejected(service, submit_subject, payment_two_id)

    instruction.approve()
    assert instruction.status == "APPROVED"

    await _submit_payment(service, submit_subject, payment_one_id)
    await _submit_payment(service, submit_subject, payment_two_id)
    assert instruction.status == "APPROVED"
    service.instruction_service.mark_used.assert_not_awaited()
    assert repo.payment_status(payment_one_id) == PaymentStatus.SUBMITTED
    assert repo.payment_status(payment_two_id) == PaymentStatus.SUBMITTED

    with _patched_txn():
        approved_one = await service.approve(payment_one_id, approver_subject)
    assert approved_one.payment.status == PaymentStatus.APPROVED

    with _patched_txn():
        approved_two = await service.approve(payment_two_id, approver_subject)
    assert approved_two.payment.status == PaymentStatus.APPROVED
