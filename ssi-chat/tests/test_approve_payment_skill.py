from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from chat_application.auth.subject import Subject
from chat_application.authz.obo import PolicyDecision
from chat_application.skills.approve_payment import (
    confirm_approve_payment,
    run_approve_payment_phase1,
)
from chat_application.skills.detect import parse_approve_payment_params
from chat_application.skills.pending_store import pending_approve_payment_store


def _funding_approver() -> Subject:
    return Subject(
        user_id="pay-400",
        given_name="Kwame",
        family_name="Osei",
        title="Partner",
        lob=None,
        roles=["FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_BILLION_CLUB"],
        covering_lobs=["FICC", "FX", "DESK_RATES"],
        supervisor_id=None,
    )


def _payment() -> dict:
    return {
        "payment_id": "20260715-FICC-P-9",
        "instruction_id": "20260715-FICC-I-1",
        "instruction_version": 2,
        "status": "SUBMITTED",
        "amount": 12_000_000.0,
        "currency": "USD",
        "value_date": "2026-07-16",
        "owning_lob": "FICC",
        "instruction_type": "STANDING",
        "created_by": {
            "user_id": "pay-101",
            "supervisor_id": "pay-201",
            "title": "Analyst",
        },
    }


def _instruction() -> dict:
    return {
        "instruction_id": "20260715-FICC-I-1",
        "status": "APPROVED",
        "owning_lob": "FICC",
        "currency": "USD",
        "end_date": "2026-12-31",
        "instruction_type": "STANDING",
        "version_number": 2,
        "debtor": {"name": "Acme Debtor LLC"},
        "debtor_account": {
            "identification_scheme": "IBAN",
            "identification": "GB00ACME0001",
        },
        "creditor": {"name": "Globex Creditor SA"},
        "creditor_account": {
            "identification_scheme": "IBAN",
            "identification": "CH00GLOBEX0002",
        },
        "intermediary_agents": [],
    }


class TestParseApprovePaymentParams:
    def test_parses_payment_id(self) -> None:
        params = parse_approve_payment_params(
            "Please approve payment 20260715-FICC-P-9."
        )
        assert params is not None
        assert params.payment_id == "20260715-FICC-P-9"

    def test_missing_payment_id(self) -> None:
        assert parse_approve_payment_params("Please approve this payment.") is None


@pytest.mark.asyncio
async def test_phase1_awaits_confirmation() -> None:
    pending_approve_payment_store.clear()
    with (
        patch(
            "chat_application.skills.approve_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.approve_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.approve_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.approve_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        payment_cls.return_value.get_payment = AsyncMock(return_value=_payment())
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(
            return_value=PolicyDecision(
                allowed=True,
                allow_basis=["FUNDING_APPROVER", "covers LOB"],
                violations=[],
                is_alert=False,
            )
        )
        result = await run_approve_payment_phase1(
            "Please approve payment 20260715-FICC-P-9.",
            subject=_funding_approver(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.pending_id is not None
    assert result.confirmation is not None
    assert result.confirmation.payment_id == "20260715-FICC-P-9"
    assert result.confirmation.payment_status == "SUBMITTED"
    assert result.intent_id == "skill.approve_payment.awaiting_confirmation"
    assert result.skill == "approve_payment"


@pytest.mark.asyncio
async def test_phase1_denied() -> None:
    pending_approve_payment_store.clear()
    with (
        patch(
            "chat_application.skills.approve_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.approve_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.approve_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.approve_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        payment_cls.return_value.get_payment = AsyncMock(return_value=_payment())
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(
            return_value=PolicyDecision(
                allowed=False,
                allow_basis=[],
                violations=["payment_creator_is_not_approver"],
                is_alert=False,
            )
        )
        result = await run_approve_payment_phase1(
            "Please approve payment 20260715-FICC-P-9.",
            subject=_funding_approver(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.pending_id is None
    assert result.intent_id == "skill.approve_payment.denied"
    assert "may not approve" in result.answer


@pytest.mark.asyncio
async def test_phase1_rejects_non_submitted() -> None:
    pending_approve_payment_store.clear()
    payment = _payment()
    payment["status"] = "DRAFT"
    with (
        patch(
            "chat_application.skills.approve_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.approve_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        payment_cls.return_value.get_payment = AsyncMock(return_value=payment)
        result = await run_approve_payment_phase1(
            "Please approve payment 20260715-FICC-P-9.",
            subject=_funding_approver(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.intent_id == "skill.approve_payment.wrong_status"
    assert "SUBMITTED" in result.answer


@pytest.mark.asyncio
async def test_confirm_no_go() -> None:
    pending_approve_payment_store.clear()
    with (
        patch(
            "chat_application.skills.approve_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.approve_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.approve_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.approve_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        payment_cls.return_value.get_payment = AsyncMock(return_value=_payment())
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(
            return_value=PolicyDecision(
                allowed=True,
                allow_basis=["ok"],
                violations=[],
                is_alert=False,
            )
        )
        phase1 = await run_approve_payment_phase1(
            "Please approve payment 20260715-FICC-P-9.",
            subject=_funding_approver(),
            user_token="user-token",
            user_session_id="sess",
        )
    assert phase1 is not None and phase1.pending_id
    result = await confirm_approve_payment(
        pending_id=phase1.pending_id,
        decision="no_go",
        subject=_funding_approver(),
        user_token="user-token",
        user_session_id="sess",
    )
    assert result.intent_id == "skill.approve_payment.cancelled"
    assert "cancelled" in result.answer.lower()


@pytest.mark.asyncio
async def test_confirm_go_approves_payment() -> None:
    pending_approve_payment_store.clear()
    approved = _payment()
    approved["status"] = "APPROVED"
    approved["approved_at"] = "2026-07-16T12:00:00Z"
    with (
        patch(
            "chat_application.skills.approve_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.approve_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.approve_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.approve_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        client = payment_cls.return_value
        client.get_payment = AsyncMock(return_value=_payment())
        client.approve_payment = AsyncMock(return_value=approved)
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(
            return_value=PolicyDecision(
                allowed=True,
                allow_basis=["ok"],
                violations=[],
                is_alert=False,
            )
        )
        phase1 = await run_approve_payment_phase1(
            "Please approve payment 20260715-FICC-P-9.",
            subject=_funding_approver(),
            user_token="user-token",
            user_session_id="sess",
        )
        assert phase1 is not None and phase1.pending_id
        result = await confirm_approve_payment(
            pending_id=phase1.pending_id,
            decision="go",
            subject=_funding_approver(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result.intent_id == "skill.approve_payment.approved"
    assert "approved" in result.answer.lower()
    client.approve_payment.assert_awaited_once()
