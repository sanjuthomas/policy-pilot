from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from chat_application.auth.subject import Subject
from chat_application.authz.obo import PolicyDecision
from chat_application.skills.create_payment import (
    confirm_create_payment,
    run_create_payment_phase1,
)
from chat_application.skills.detect import parse_create_payment_params
from chat_application.skills.pending_store import pending_create_payment_store


def _creator() -> Subject:
    return Subject(
        user_id="pay-101",
        given_name="Emily",
        family_name="Rodriguez",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE", "UP_TO_100_MILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
        supervisor_id="pay-201",
    )


def _instruction() -> dict:
    return {
        "instruction_id": "20260705-FX-I-12",
        "status": "APPROVED",
        "owning_lob": "FX",
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


class TestParseCreatePaymentParams:
    def test_parses_actionable_create(self) -> None:
        params = parse_create_payment_params(
            "Can you create a payment using instruction 20260705-FX-I-12? "
            "Value date today and amount 10 million."
        )
        assert params is not None
        assert params.instruction_id == "20260705-FX-I-12"
        assert params.amount == 10_000_000
        assert params.value_date == date.today().isoformat()

    def test_parses_tomorrow_and_currency_suffix(self) -> None:
        params = parse_create_payment_params(
            "Can you create a payment for instruction ID 20260705-FICC-I-31? "
            "Value date tomorrow; amount: 12 million USD."
        )
        assert params is not None
        assert params.instruction_id == "20260705-FICC-I-31"
        assert params.amount == 12_000_000
        assert params.value_date == (date.today() + timedelta(days=1)).isoformat()

    def test_requires_slots(self) -> None:
        assert parse_create_payment_params("Can I create a payment?") is None
        assert (
            parse_create_payment_params(
                "Create a payment using instruction 20260705-FX-I-12 value date today"
            )
            is None
        )


@pytest.mark.asyncio
async def test_phase1_awaits_confirmation() -> None:
    pending_create_payment_store.clear()
    subject = _creator()
    decision = PolicyDecision(
        allowed=True,
        allow_basis=[
            "amount 1.2e+07 within subject and absolute limits",
            "covers LOB FICC",
            "role PAYMENT_CREATOR",
        ],
        violations=[],
        is_alert=False,
    )
    with (
        patch(
            "chat_application.skills.create_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.create_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.create_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(return_value=decision)

        result = await run_create_payment_phase1(
            "Can you create a payment using instruction 20260705-FX-I-12? "
            "Value date today and amount 10 million.",
            subject=subject,
            user_token="user-token",
            user_session_id="user-session",
        )

    assert result is not None
    assert result.pending_id
    assert result.confirmation is not None
    assert result.confirmation.debtor_name == "Acme Debtor LLC"
    assert "Correspondent Bank" in result.confirmation.intermediaries[0]
    assert result.intent_id == "skill.create_payment.awaiting_confirmation"
    assert any("Yes" in line for line in result.activities)
    assert any("$12 million" in line or "12,000,000" in line or "$12,000,000" in line for line in result.activities)
    assert not any("1.2e+07" in line for line in result.activities)


@pytest.mark.asyncio
async def test_phase1_denied_stops() -> None:
    pending_create_payment_store.clear()
    subject = _creator()
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["AMOUNT exceeds club"],
        is_alert=True,
    )
    with (
        patch(
            "chat_application.skills.create_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.create_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.create_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(return_value=decision)

        result = await run_create_payment_phase1(
            "Create a payment using instruction 20260705-FX-I-12 "
            "amount 10 million value date today",
            subject=subject,
            user_token="user-token",
            user_session_id="user-session",
        )

    assert result is not None
    assert result.pending_id is None
    assert result.intent_id == "skill.create_payment.denied"
    assert "No payment was created" in result.answer


@pytest.mark.asyncio
async def test_confirm_no_go() -> None:
    pending_create_payment_store.clear()
    subject = _creator()
    decision = PolicyDecision(True, ["ok"], [], False)
    with (
        patch(
            "chat_application.skills.create_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.create_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.create_payment.service_identity"
        ) as identity,
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(return_value=decision)
        phase1 = await run_create_payment_phase1(
            "Create a payment using instruction 20260705-FX-I-12 "
            "amount 1 million value date today",
            subject=subject,
            user_token="user-token",
            user_session_id="user-session",
        )

    assert phase1 and phase1.pending_id
    result = await confirm_create_payment(
        pending_id=phase1.pending_id,
        decision="no_go",
        subject=subject,
        user_token="user-token",
        user_session_id="user-session",
    )
    assert result.intent_id == "skill.create_payment.cancelled"
    assert "No payment was created" in result.answer


@pytest.mark.asyncio
async def test_confirm_go_creates_payment() -> None:
    pending_create_payment_store.clear()
    subject = _creator()
    decision = PolicyDecision(True, ["ok"], [], False)
    with (
        patch(
            "chat_application.skills.create_payment.InstructionClient"
        ) as instruction_cls,
        patch(
            "chat_application.skills.create_payment.AuthzOboClient"
        ) as authz_cls,
        patch(
            "chat_application.skills.create_payment.PaymentClient"
        ) as payment_cls,
        patch(
            "chat_application.skills.create_payment.service_identity"
        ) as identity,
        patch(
            "chat_application.skills.create_payment._eligible_approvers_section",
            new_callable=AsyncMock,
            return_value="### Who can approve\n\nok",
        ),
    ):
        identity.token = "svc-token"
        identity.session_id = "svc-session"
        instruction_cls.return_value.get_instruction = AsyncMock(
            return_value=_instruction()
        )
        authz_cls.return_value.evaluate_payment = AsyncMock(return_value=decision)
        payment_cls.return_value.create_payment = AsyncMock(
            return_value={
                "payment_id": "20260712-FX-P-99",
                "instruction_id": "20260705-FX-I-12",
                "amount": 1_000_000,
                "currency": "USD",
                "owning_lob": "FX",
                "status": "DRAFT",
                "created_by": {"user_id": "pay-101"},
            }
        )
        phase1 = await run_create_payment_phase1(
            "Create a payment using instruction 20260705-FX-I-12 "
            "amount 1 million value date today",
            subject=subject,
            user_token="user-token",
            user_session_id="user-session",
        )
        assert phase1 and phase1.pending_id
        result = await confirm_create_payment(
            pending_id=phase1.pending_id,
            decision="go",
            subject=subject,
            user_token="user-token",
            user_session_id="user-session",
        )

    assert result.intent_id == "skill.create_payment.created"
    assert "20260712-FX-P-99" in result.answer
    payment_cls.return_value.create_payment.assert_awaited_once()
