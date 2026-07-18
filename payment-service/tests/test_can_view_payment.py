from __future__ import annotations

from datetime import datetime, timezone

from ps.models.api import Subject
from ps.models.enums import PaymentStatus
from ps.models.payment import Payment, UserReference
from ps.service import _can_view_payment


def _payment(*, owning_lob: str = "FICC", created_by: str = "pay-101") -> Payment:
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


def test_mo_views_via_covering_lobs_only() -> None:
    mo = Subject(
        user_id="pay-101",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        lob="FICC",  # desk lob must be ignored for MO
        covering_lobs=["FX"],
    )
    other = _payment(owning_lob="FICC", created_by="someone-else")
    assert _can_view_payment(mo, other) is False
    assert _can_view_payment(mo, _payment(owning_lob="FX", created_by="someone-else")) is True


def test_fo_views_via_subject_lob_not_covering() -> None:
    fo = Subject(
        user_id="fo-ficc-101",
        title="Desk Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=[],
        lob="FICC",
        covering_lobs=["FX"],  # covering must be ignored for non-MO
    )
    assert _can_view_payment(fo, _payment(owning_lob="FICC")) is True
    assert _can_view_payment(fo, _payment(owning_lob="FX")) is False


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
