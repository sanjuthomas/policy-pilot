from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from chat_application.auth.subject import Subject
from chat_application.authz.obo import PolicyDecision
from chat_application.skills.cancel_payment import (
    confirm_cancel_payment,
    run_cancel_payment_phase1,
)
from chat_application.skills.detect import parse_cancel_payment_params
from chat_application.skills.payment_client import (
    PaymentCancelDenied,
    PaymentClientError,
)
from chat_application.skills.pending_store import pending_cancel_payment_store


def _mo_creator() -> Subject:
    return Subject(
        user_id="pay-101",
        given_name="Amina",
        family_name="Diallo",
        title="Analyst",
        lob="FICC",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FICC"],
        supervisor_id="pay-201",
    )


def _fo_creator() -> Subject:
    return Subject(
        user_id="fo-ficc-101",
        given_name="Front",
        family_name="Office",
        title="Desk Analyst",
        lob="FICC",
        roles=["PAYMENT_CREATOR"],
        groups=["FRONT_OFFICE"],
        covering_lobs=["FICC"],
        supervisor_id="pay-201",
    )


def _payment(*, status: str = "DRAFT") -> dict:
    return {
        "payment_id": "20260715-FICC-P-9",
        "instruction_id": "20260715-FICC-I-1",
        "instruction_version": 2,
        "status": status,
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


class TestParseCancelPaymentParams:
    def test_parses_payment_id(self) -> None:
        params = parse_cancel_payment_params(
            "Please cancel payment 20260715-FICC-P-9."
        )
        assert params is not None
        assert params.payment_id == "20260715-FICC-P-9"

    def test_missing_payment_id(self) -> None:
        assert parse_cancel_payment_params("Please cancel this payment.") is None


@pytest.mark.asyncio
async def test_phase1_forbidden_without_middle_office() -> None:
    pending_cancel_payment_store.clear()
    result = await run_cancel_payment_phase1(
        "Please cancel payment 20260715-FICC-P-9.",
        subject=_fo_creator(),
        user_token="user-token",
        user_session_id="sess",
    )
    assert result is not None
    assert result.pending_id is None
    assert result.intent_id == "skill.cancel_payment.forbidden"
    assert "MIDDLE_OFFICE" in result.answer


@pytest.mark.asyncio
async def test_phase1_awaits_confirmation() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
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
                allow_basis=["PAYMENT_CREATOR", "MIDDLE_OFFICE", "covers LOB"],
                violations=[],
                is_alert=False,
            )
        )
        result = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.pending_id is not None
    assert result.confirmation is not None
    assert result.confirmation.payment_id == "20260715-FICC-P-9"
    assert result.confirmation.payment_status == "DRAFT"
    assert result.intent_id == "skill.cancel_payment.awaiting_confirmation"
    assert result.skill == "cancel_payment"


@pytest.mark.asyncio
async def test_phase1_denied() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
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
                violations=["subject_does_not_cover_lob"],
                is_alert=False,
            )
        )
        result = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.pending_id is None
    assert result.intent_id == "skill.cancel_payment.denied"
    assert "may not cancel" in result.answer


@pytest.mark.asyncio
async def test_phase1_rejects_approved() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        payment_cls.return_value.get_payment = AsyncMock(
            return_value=_payment(status="APPROVED")
        )
        result = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.intent_id == "skill.cancel_payment.wrong_status"
    assert "APPROVED" in result.answer


@pytest.mark.asyncio
async def test_confirm_no_go() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
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
        phase1 = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )
    assert phase1 is not None and phase1.pending_id
    result = await confirm_cancel_payment(
        pending_id=phase1.pending_id,
        decision="no_go",
        subject=_mo_creator(),
        user_token="user-token",
        user_session_id="sess",
    )
    assert result.intent_id == "skill.cancel_payment.no_go"
    assert "No Go" in result.answer


@pytest.mark.asyncio
async def test_confirm_go_cancels_payment() -> None:
    pending_cancel_payment_store.clear()
    cancelled = _payment()
    cancelled["status"] = "CANCELLED"
    cancelled["cancelled_at"] = "2026-07-16T12:00:00Z"
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        client = payment_cls.return_value
        client.get_payment = AsyncMock(return_value=_payment())
        client.cancel_payment = AsyncMock(return_value=cancelled)
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
        phase1 = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )
        assert phase1 is not None and phase1.pending_id
        result = await confirm_cancel_payment(
            pending_id=phase1.pending_id,
            decision="go",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result.intent_id == "skill.cancel_payment.cancelled"
    assert "cancelled" in result.answer.lower()
    client.cancel_payment.assert_awaited_once()


@pytest.mark.asyncio
async def test_phase1_accepts_submitted() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        payment_cls.return_value.get_payment = AsyncMock(
            return_value=_payment(status="SUBMITTED")
        )
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
        result = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.intent_id == "skill.cancel_payment.awaiting_confirmation"
    assert result.confirmation is not None
    assert result.confirmation.payment_status == "SUBMITTED"


@pytest.mark.asyncio
async def test_confirm_go_cancel_denied() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        client = payment_cls.return_value
        client.get_payment = AsyncMock(return_value=_payment())
        client.cancel_payment = AsyncMock(
            side_effect=PaymentCancelDenied("not allowed")
        )
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
        phase1 = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )
        assert phase1 is not None and phase1.pending_id
        result = await confirm_cancel_payment(
            pending_id=phase1.pending_id,
            decision="go",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result.intent_id == "skill.cancel_payment.cancel_denied"
    assert "not allowed" in result.answer


@pytest.mark.asyncio
async def test_confirm_pending_missing() -> None:
    pending_cancel_payment_store.clear()
    result = await confirm_cancel_payment(
        pending_id="missing",
        decision="go",
        subject=_mo_creator(),
        user_token="user-token",
        user_session_id="sess",
    )
    assert result.intent_id == "skill.cancel_payment.pending_missing"


@pytest.mark.asyncio
async def test_confirm_pending_forbidden_and_bad_decision() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
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
        phase1 = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )
    assert phase1 is not None and phase1.pending_id

    other = _mo_creator().model_copy(update={"user_id": "pay-999"})
    forbidden = await confirm_cancel_payment(
        pending_id=phase1.pending_id,
        decision="go",
        subject=other,
        user_token="user-token",
        user_session_id="sess",
    )
    assert forbidden.intent_id == "skill.cancel_payment.pending_forbidden"

    bad = await confirm_cancel_payment(
        pending_id=phase1.pending_id,
        decision="maybe",
        subject=_mo_creator(),
        user_token="user-token",
        user_session_id="sess",
    )
    assert bad.intent_id == "skill.cancel_payment.bad_decision"


@pytest.mark.asyncio
async def test_confirm_go_client_error() -> None:
    pending_cancel_payment_store.clear()
    with (
        patch(
            "chat_application.skills.cancel_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.cancel_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.cancel_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.cancel_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        client = payment_cls.return_value
        client.get_payment = AsyncMock(return_value=_payment())
        client.cancel_payment = AsyncMock(
            side_effect=PaymentClientError("payment-service down")
        )
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
        phase1 = await run_cancel_payment_phase1(
            "Please cancel payment 20260715-FICC-P-9.",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )
        assert phase1 is not None and phase1.pending_id
        result = await confirm_cancel_payment(
            pending_id=phase1.pending_id,
            decision="go",
            subject=_mo_creator(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result.intent_id == "skill.cancel_payment.cancel_error"
    assert "payment-service down" in result.answer
