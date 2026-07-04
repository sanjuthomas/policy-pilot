from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from ps.models.payment import Payment
from ps.service import (
    _APPROVED_STATUSES,
    _DRAFT_PAYMENT_INSTRUCTION_STATUSES,
    _check_instruction_validity_for_approval,
    _validate_instruction_at_create,
    _validate_instruction_approved_for_submit,
    _validate_instruction_for_draft_payment,
)


def test_approved_statuses_constant() -> None:
    assert _APPROVED_STATUSES == {"APPROVED"}


def test_draft_payment_instruction_statuses_constant() -> None:
    assert _DRAFT_PAYMENT_INSTRUCTION_STATUSES == {"DRAFT", "SUBMITTED", "APPROVED"}


def test_validate_instruction_at_create_approved(standing_instruction: dict) -> None:
    _validate_instruction_at_create(standing_instruction)


def test_validate_instruction_at_create_single_use(standing_instruction: dict) -> None:
    standing_instruction["instruction_type"] = "SINGLE_USE"
    _validate_instruction_at_create(standing_instruction)


def test_validate_instruction_at_create_allows_draft(standing_instruction: dict) -> None:
    standing_instruction["status"] = "DRAFT"
    _validate_instruction_at_create(standing_instruction)


def test_validate_instruction_at_create_allows_submitted(standing_instruction: dict) -> None:
    standing_instruction["status"] = "SUBMITTED"
    _validate_instruction_at_create(standing_instruction)


def test_validate_instruction_at_create_rejects_used(standing_instruction: dict) -> None:
    standing_instruction["status"] = "USED"
    with pytest.raises(ValueError, match="not in a usable state"):
        _validate_instruction_at_create(standing_instruction)


def test_validate_instruction_at_create_rejects_expired(standing_instruction: dict) -> None:
    past = datetime.now(timezone.utc) - timedelta(days=1)
    standing_instruction["end_date"] = past.isoformat()
    with pytest.raises(ValueError, match="instruction has expired"):
        _validate_instruction_at_create(standing_instruction)


def test_validate_instruction_at_create_allows_no_end_date(standing_instruction: dict) -> None:
    standing_instruction["end_date"] = ""
    _validate_instruction_at_create(standing_instruction)


def test_check_instruction_validity_returns_none_when_valid(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    assert _check_instruction_validity_for_approval(payment, standing_instruction) is None


def test_check_instruction_validity_version_drift(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    standing_instruction["version_number"] = 2
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "version 1" in reason
    assert "current version is 2" in reason


def test_check_instruction_validity_bad_status(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    standing_instruction["status"] = "SUSPENDED"
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "no longer in an approvable state" in reason


def test_check_instruction_validity_allows_used_single_use(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    payment.instruction_type = "SINGLE_USE"
    standing_instruction["status"] = "USED"
    standing_instruction["instruction_type"] = "SINGLE_USE"
    assert _check_instruction_validity_for_approval(payment, standing_instruction) is None


def test_validate_instruction_approved_for_submit(standing_instruction: dict) -> None:
    _validate_instruction_approved_for_submit(standing_instruction)


def test_validate_instruction_approved_for_submit_rejects_draft(
    standing_instruction: dict,
) -> None:
    standing_instruction["status"] = "DRAFT"
    with pytest.raises(ValueError, match="must be APPROVED"):
        _validate_instruction_approved_for_submit(standing_instruction)


def test_validate_instruction_for_draft_payment_rejects_used(
    standing_instruction: dict,
) -> None:
    standing_instruction["status"] = "USED"
    with pytest.raises(ValueError, match="not in a usable state"):
        _validate_instruction_for_draft_payment(standing_instruction)


def test_check_instruction_validity_expired(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    standing_instruction["end_date"] = past.isoformat()
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "instruction has expired" in reason


def test_check_instruction_validity_unparseable_end_date(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    standing_instruction["end_date"] = "not-a-date"
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "unparseable end_date" in reason


def test_check_instruction_validity_not_yet_effective(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    future = datetime.now(timezone.utc) + timedelta(days=10)
    standing_instruction["effective_date"] = future.isoformat()
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "not yet effective" in reason


def test_check_instruction_validity_unparseable_effective_date(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    standing_instruction["effective_date"] = "bad-date"
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "unparseable effective_date" in reason


def test_check_instruction_validity_empty_type_skips_check(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    standing_instruction.pop("instruction_type", None)
    assert _check_instruction_validity_for_approval(payment, standing_instruction) is None


def test_check_instruction_validity_type_changed(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    standing_instruction["instruction_type"] = "SINGLE_USE"
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "instruction type changed" in reason


def test_check_instruction_validity_naive_end_date(
    payment: Payment,
    standing_instruction: dict,
) -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    standing_instruction["end_date"] = past.replace(tzinfo=None).isoformat()
    reason = _check_instruction_validity_for_approval(payment, standing_instruction)
    assert reason is not None
    assert "instruction has expired" in reason
