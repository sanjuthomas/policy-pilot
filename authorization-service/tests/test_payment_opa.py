from __future__ import annotations

from authz.payment_opa import (
    payment_approval_blocked_reason,
    payment_prospective_instruction_status,
)


def test_payment_approval_blocked_reason_for_used_instruction() -> None:
    reason = payment_approval_blocked_reason(
        "DRAFT",
        "USED",
        instruction_id="20260704-FICC-I-6",
    )
    assert reason is not None
    assert "20260704-FICC-I-6" in reason
    assert "USED" in reason
    assert "cannot support" in reason


def test_payment_approval_blocked_reason_for_draft_payment() -> None:
    reason = payment_approval_blocked_reason("DRAFT", "APPROVED")
    assert reason == (
        "Payment approval is not permitted while status is DRAFT. "
        "Submit the payment first."
    )


def test_payment_approval_blocked_reason_for_submitted_payment() -> None:
    assert payment_approval_blocked_reason("SUBMITTED", "APPROVED") is None


def test_payment_prospective_instruction_status_only_when_approved() -> None:
    assert payment_prospective_instruction_status("APPROVED") == "APPROVED"
    assert payment_prospective_instruction_status("USED") is None
