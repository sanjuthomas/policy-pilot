from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from chat_application.auth.subject import Subject
from chat_application.skills.create_payment import (
    _clubs,
    _display,
    confirm_create_payment,
    run_create_payment_phase1,
)
from chat_application.skills.instruction_client import (
    InstructionClientError,
    InstructionNotFoundError,
)
from chat_application.skills.models import CreatePaymentParams
from chat_application.skills.pending_store import (
    build_pending,
    pending_create_payment_store,
)


def _params() -> CreatePaymentParams:
    return CreatePaymentParams(
        instruction_id="instruction-1",
        amount=10.0,
        value_date="2026-07-12",
    )


@pytest.mark.asyncio
async def test_phase1_returns_none_without_payment_parameters() -> None:
    subject = Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"])
    assert (
        await run_create_payment_phase1(
            "not a payment request",
            subject=subject,
            user_token="token",
            user_session_id=None,
        )
        is None
    )


@pytest.mark.asyncio
async def test_phase1_rejects_subject_without_creator_role() -> None:
    subject = Subject(user_id="viewer", title="Analyst", roles=["COMPLIANCE_ANALYST"])
    result = await run_create_payment_phase1(
        "ignored",
        params=_params(),
        subject=subject,
        user_token="token",
        user_session_id=None,
    )
    assert result is not None
    assert result.intent_id == "skill.create_payment.forbidden"


@pytest.mark.asyncio
async def test_phase1_requires_a_user_token() -> None:
    subject = Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"])
    result = await run_create_payment_phase1(
        "ignored",
        params=_params(),
        subject=subject,
        user_token=None,
        user_session_id=None,
    )
    assert result is not None
    assert result.intent_id == "skill.create_payment.auth_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "intent_id"),
    [
        (InstructionNotFoundError("missing"), "skill.create_payment.instruction_missing"),
        (InstructionClientError("down"), "skill.create_payment.instruction_error"),
    ],
)
async def test_phase1_handles_instruction_lookup_failures(error, intent_id: str) -> None:
    subject = Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"])
    with patch("chat_application.skills.create_payment.InstructionClient") as client:
        client.return_value.get_instruction = AsyncMock(side_effect=error)
        result = await run_create_payment_phase1(
            "ignored",
            params=_params(),
            subject=subject,
            user_token="token",
            user_session_id=None,
        )
    assert result is not None
    assert result.intent_id == intent_id


@pytest.mark.asyncio
async def test_confirm_returns_expired_result_for_unknown_pending_id() -> None:
    result = await confirm_create_payment(
        pending_id="unknown",
        decision="go",
        subject=Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"]),
        user_token="token",
        user_session_id=None,
    )
    assert result.intent_id == "skill.create_payment.pending_missing"


@pytest.mark.asyncio
async def test_confirm_rejects_pending_owned_by_another_user() -> None:
    pending_create_payment_store.clear()
    pending = build_pending(
        user_id="owner",
        instruction_id="instruction-1",
        amount=10.0,
        value_date="2026-07-12",
        currency="USD",
        owning_lob="FX",
        instruction_status="APPROVED",
        instruction_end_date="2026-12-31",
        instruction_type="STANDING",
        instruction_version=1,
        card=None,
    )
    pending_create_payment_store.put(pending)
    result = await confirm_create_payment(
        pending_id=pending.pending_id,
        decision="go",
        subject=Subject(user_id="other", title="Analyst", roles=["PAYMENT_CREATOR"]),
        user_token="token",
        user_session_id=None,
    )
    assert result.intent_id == "skill.create_payment.pending_forbidden"


@pytest.mark.asyncio
async def test_confirm_rejects_an_invalid_decision() -> None:
    pending_create_payment_store.clear()
    pending = build_pending(
        user_id="creator",
        instruction_id="instruction-1",
        amount=10.0,
        value_date="2026-07-12",
        currency="USD",
        owning_lob="FX",
        instruction_status="APPROVED",
        instruction_end_date="2026-12-31",
        instruction_type="STANDING",
        instruction_version=1,
        card=None,
    )
    pending_create_payment_store.put(pending)
    result = await confirm_create_payment(
        pending_id=pending.pending_id,
        decision="maybe",
        subject=Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"]),
        user_token="token",
        user_session_id=None,
    )
    assert result.intent_id == "skill.create_payment.bad_decision"


@pytest.mark.asyncio
async def test_confirm_requires_a_user_token() -> None:
    pending_create_payment_store.clear()
    pending = build_pending(
        user_id="creator",
        instruction_id="instruction-1",
        amount=10.0,
        value_date="2026-07-12",
        currency="USD",
        owning_lob="FX",
        instruction_status="APPROVED",
        instruction_end_date="2026-12-31",
        instruction_type="STANDING",
        instruction_version=1,
        card=None,
    )
    pending_create_payment_store.put(pending)
    result = await confirm_create_payment(
        pending_id=pending.pending_id,
        decision="go",
        subject=Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"]),
        user_token=None,
        user_session_id=None,
    )
    assert result.intent_id == "skill.create_payment.auth_error"


@pytest.mark.asyncio
async def test_confirm_cancels_on_no_go() -> None:
    pending_create_payment_store.clear()
    pending = build_pending(
        user_id="creator",
        instruction_id="instruction-1",
        amount=10.0,
        value_date="2026-07-12",
        currency="USD",
        owning_lob="FX",
        instruction_status="APPROVED",
        instruction_end_date="2026-12-31",
        instruction_type="STANDING",
        instruction_version=1,
        card=None,
    )
    pending_create_payment_store.put(pending)
    result = await confirm_create_payment(
        pending_id=pending.pending_id,
        decision="no_go",
        subject=Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"]),
        user_token="token",
        user_session_id=None,
    )
    assert result.intent_id == "skill.create_payment.cancelled"


def test_display_and_club_helpers() -> None:
    full_name = Subject(
        user_id="creator",
        given_name="First",
        family_name="Last",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["UP_TO_10_MILLION_CLUB", "OPERATIONS"],
    )
    assert _display(full_name) == "Last, First"
    assert (
        _display(Subject(user_id="creator", title="Analyst", roles=["PAYMENT_CREATOR"]))
        == "creator"
    )
    assert _clubs(full_name) == ["UP_TO_10_MILLION_CLUB"]
