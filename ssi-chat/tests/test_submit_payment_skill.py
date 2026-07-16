from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from chat_application.auth.subject import Subject
from chat_application.authz.obo import PolicyDecision
from chat_application.skills.detect import parse_submit_payment_params
from chat_application.skills.pending_store import pending_submit_payment_store
from chat_application.skills.submit_payment import (
    confirm_submit_payment,
    run_submit_payment_phase1,
)


def _fo_submitter() -> Subject:
    return Subject(
        user_id="fo-ficc-101",
        given_name="Alex",
        family_name="Nguyen",
        title="Desk Analyst",
        lob="FICC",
        roles=["PAYMENT_CREATOR"],
        groups=[],
        covering_lobs=[],
        supervisor_id="ficc-300",
    )


def _payment() -> dict:
    return {
        "payment_id": "20260715-FICC-P-9",
        "instruction_id": "20260715-FICC-I-1",
        "instruction_version": 2,
        "status": "DRAFT",
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
        "intermediary_agents": [
            {
                "agent": {
                    "financial_institution": {
                        "name": "Correspondent Bank",
                        "identification": "CORRUS33",
                    }
                },
                "account": {
                    "identification_scheme": "BBAN",
                    "identification": "998877",
                },
            }
        ],
    }


class TestParseSubmitPaymentParams:
    def test_parses_payment_id(self) -> None:
        params = parse_submit_payment_params(
            "Please submit payment 20260715-FICC-P-9 for approval."
        )
        assert params is not None
        assert params.payment_id == "20260715-FICC-P-9"

    def test_missing_payment_id(self) -> None:
        assert parse_submit_payment_params("Please submit this payment for approval.") is None


@pytest.mark.asyncio
async def test_phase1_awaits_confirmation() -> None:
    pending_submit_payment_store.clear()
    payment = _payment()
    instruction = _instruction()
    with (
        patch(
            "chat_application.skills.submit_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.submit_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.submit_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.submit_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        payment_cls.return_value.get_payment = AsyncMock(return_value=payment)
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=instruction
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(
            return_value=PolicyDecision(
                allowed=True,
                allow_basis=["PAYMENT_CREATOR", "desk LOB matches"],
                violations=[],
                is_alert=False,
            )
        )
        result = await run_submit_payment_phase1(
            "Please submit payment 20260715-FICC-P-9 for approval.",
            subject=_fo_submitter(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.pending_id is not None
    assert result.confirmation is not None
    assert result.confirmation.payment_id == "20260715-FICC-P-9"
    assert result.confirmation.debtor_name == "Acme Debtor LLC"
    assert "Correspondent Bank" in result.confirmation.intermediaries[0]
    assert result.intent_id == "skill.submit_payment.awaiting_confirmation"
    assert result.skill == "submit_payment"


@pytest.mark.asyncio
async def test_phase1_denied() -> None:
    pending_submit_payment_store.clear()
    with (
        patch(
            "chat_application.skills.submit_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.submit_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.submit_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.submit_payment.service_identity"
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
                violations=["desk LOB mismatch"],
                is_alert=False,
            )
        )
        result = await run_submit_payment_phase1(
            "Please submit payment 20260715-FICC-P-9 for approval.",
            subject=_fo_submitter(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.pending_id is None
    assert result.intent_id == "skill.submit_payment.denied"
    assert "may not submit" in result.answer


@pytest.mark.asyncio
async def test_phase1_rejects_non_draft() -> None:
    pending_submit_payment_store.clear()
    payment = _payment()
    payment["status"] = "SUBMITTED"
    with (
        patch(
            "chat_application.skills.submit_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.submit_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        payment_cls.return_value.get_payment = AsyncMock(return_value=payment)
        result = await run_submit_payment_phase1(
            "Please submit payment 20260715-FICC-P-9 for approval.",
            subject=_fo_submitter(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result is not None
    assert result.intent_id == "skill.submit_payment.wrong_status"
    assert "DRAFT" in result.answer


@pytest.mark.asyncio
async def test_confirm_no_go() -> None:
    pending_submit_payment_store.clear()
    with (
        patch(
            "chat_application.skills.submit_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.submit_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.submit_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.submit_payment.service_identity"
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
        phase1 = await run_submit_payment_phase1(
            "Please submit payment 20260715-FICC-P-9 for approval.",
            subject=_fo_submitter(),
            user_token="user-token",
            user_session_id="sess",
        )
    assert phase1 is not None and phase1.pending_id
    result = await confirm_submit_payment(
        pending_id=phase1.pending_id,
        decision="no_go",
        subject=_fo_submitter(),
        user_token="user-token",
        user_session_id="sess",
    )
    assert result.intent_id == "skill.submit_payment.cancelled"
    assert "cancelled" in result.answer.lower()


@pytest.mark.asyncio
async def test_confirm_go_submits_payment() -> None:
    pending_submit_payment_store.clear()
    submitted = _payment()
    submitted["status"] = "SUBMITTED"
    with (
        patch(
            "chat_application.skills.submit_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.submit_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.submit_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.submit_payment.service_identity"
        ) as identity,
        patch(
            "chat_application.skills.submit_payment._eligible_approvers_section",
            new=AsyncMock(return_value="### Who can approve"),
        ),
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        client = payment_cls.return_value
        client.get_payment = AsyncMock(return_value=_payment())
        client.submit_payment = AsyncMock(return_value=submitted)
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
        phase1 = await run_submit_payment_phase1(
            "Please submit payment 20260715-FICC-P-9 for approval.",
            subject=_fo_submitter(),
            user_token="user-token",
            user_session_id="sess",
        )
        assert phase1 is not None and phase1.pending_id
        result = await confirm_submit_payment(
            pending_id=phase1.pending_id,
            decision="go",
            subject=_fo_submitter(),
            user_token="user-token",
            user_session_id="sess",
        )

    assert result.intent_id == "skill.submit_payment.submitted"
    assert "submitted" in result.answer.lower()
    client.submit_payment.assert_awaited_once()
