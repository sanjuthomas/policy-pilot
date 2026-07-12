from __future__ import annotations

import pytest
from chat_application.me.handlers import dispatch_me_intent, try_me_intent
from chat_application.me.models import MeIntent
from chat_application.subject import Subject


def _subject(*roles: str) -> Subject:
    return Subject(
        user_id="user-1",
        title="Analyst",
        roles=list(roles),
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FX"],
    )


@pytest.mark.asyncio
async def test_try_me_intent_returns_none_when_no_intent_matches() -> None:
    assert (
        await try_me_intent("unrelated question", subject=_subject("PAYMENT_CREATOR"))
        is None
    )


@pytest.mark.asyncio
async def test_dispatch_waiting_for_me_for_approver() -> None:
    result = await dispatch_me_intent(
        MeIntent(kind="waiting_for_me"), subject=_subject("FUNDING_APPROVER")
    )
    assert result is not None
    assert result.intent_id == "me.waiting_for_me.pending"


@pytest.mark.asyncio
async def test_dispatch_entity_actions_and_missing_ids() -> None:
    creator = _subject("PAYMENT_CREATOR")
    submitted = await dispatch_me_intent(
        MeIntent(kind="can_act_on_entity", action="SUBMIT", entity_type="payment"),
        subject=creator,
    )
    missing = await dispatch_me_intent(
        MeIntent(kind="can_act_on_entity", action="UPDATE", entity_type="payment"),
        subject=creator,
    )
    denied = await dispatch_me_intent(
        MeIntent(
            kind="can_act_on_entity",
            action="APPROVE",
            entity_type="payment",
            entity_id="p1",
        ),
        subject=creator,
    )
    assert submitted is not None
    assert missing is not None
    assert denied is not None
    assert missing.intent_id == "me.can_act_on_entity.need_id"
    assert denied.intent_id == "me.can_act_on_entity.not_approver"


@pytest.mark.asyncio
async def test_dispatch_approver_and_who_else_paths() -> None:
    approver = _subject("FUNDING_APPROVER")
    pending = await dispatch_me_intent(
        MeIntent(
            kind="can_act_on_entity",
            action="APPROVE",
            entity_type="payment",
            entity_id="p1",
        ),
        subject=approver,
    )
    missing = await dispatch_me_intent(
        MeIntent(kind="who_else_can_act", action="APPROVE", entity_type="payment"),
        subject=approver,
    )
    other = await dispatch_me_intent(
        MeIntent(
            kind="who_else_can_act",
            action="APPROVE",
            entity_type="payment",
            entity_id="p1",
        ),
        subject=approver,
    )
    assert pending is not None
    assert missing is not None
    assert other is not None
    assert pending.intent_id == "me.can_act_on_entity.pending"
    assert missing.intent_id == "me.who_else_can_act.need_id"
    assert other.intent_id == "me.who_else_can_act.pending"
