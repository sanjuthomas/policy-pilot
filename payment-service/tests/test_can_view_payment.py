from __future__ import annotations

from datetime import datetime, timezone

from ps.models.api import Subject
from ps.models.enums import PaymentStatus
from ps.models.payment import Payment, UserReference
from ps.service import _can_view_payment


def _payment(*, owning_lob: str = "FICC", created_by: str = "other-user") -> Payment:
    return Payment(
        payment_id="20260718-FICC-P-1",
        instruction_id="20260718-FICC-I-1",
        instruction_version=1,
        instruction_type="STANDING",
        status=PaymentStatus.DRAFT,
        amount=1_000_000,
        currency="USD",
        value_date="2026-07-20",
        owning_lob=owning_lob,
        created_by=UserReference(user_id=created_by, title="Analyst"),
        created_at=datetime.now(timezone.utc),
    )


def test_mo_positive_covering_includes_owning_lob() -> None:
    mo = Subject(
        user_id="pay-101",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FICC", "FX"],
    )
    assert _can_view_payment(mo, _payment(owning_lob="FICC")) is True


def test_mo_negative_covering_misses_owning_lob() -> None:
    mo = Subject(
        user_id="pay-203",
        title="Associate",
        roles=["PAYMENT_CREATOR", "FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FX"],
    )
    assert _can_view_payment(mo, _payment(owning_lob="FICC")) is False


def test_mo_negative_desk_lob_ignored_without_covering() -> None:
    mo = Subject(
        user_id="pay-orphan",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        lob="FICC",
        covering_lobs=[],
    )
    assert _can_view_payment(mo, _payment(owning_lob="FICC")) is False


def test_fo_positive_matching_desk_lob() -> None:
    fo = Subject(
        user_id="fo-ficc-101",
        title="Desk Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=[],
        lob="FICC",
        covering_lobs=["FX"],  # must be ignored
    )
    assert _can_view_payment(fo, _payment(owning_lob="FICC")) is True


def test_fo_negative_wrong_desk_lob() -> None:
    fo = Subject(
        user_id="fo-fx-101",
        title="Desk Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=[],
        lob="FX",
        covering_lobs=["FICC"],  # must be ignored
    )
    assert _can_view_payment(fo, _payment(owning_lob="FICC")) is False


def test_creator_and_admin_bypass_lob_gates() -> None:
    creator = Subject(
        user_id="pay-101",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=[],
    )
    assert _can_view_payment(creator, _payment(created_by="pay-101")) is True

    admin = Subject(
        user_id="admin-001",
        title="Admin",
        roles=["PLATFORM_ADMIN"],
        groups=["ADMIN"],
    )
    assert _can_view_payment(admin, _payment()) is True


def test_compliance_may_view_any_lob_without_covering() -> None:
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
        groups=["COMPLIANCE"],
    )
    assert _can_view_payment(compliance, _payment(owning_lob="FICC")) is True
    assert _can_view_payment(compliance, _payment(owning_lob="FX")) is True
    assert _can_view_payment(compliance, _payment(owning_lob="DESK_RATES")) is True
