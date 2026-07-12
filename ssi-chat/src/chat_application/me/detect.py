from __future__ import annotations

import re
from typing import Literal

from chat_application.cypher import (
    extract_entity_ids,
    extract_payment_ids,
    lob_filter_from_question,
)
from chat_application.me.models import MeIntent

_WHO_AM_I = re.compile(
    r"^\s*("
    r"who am i\??|"
    r"who'?s logged in\??|"
    r"who is logged in\??|"
    r"what('s| is) my (user )?id\??|"
    r"what is my (name|identity|account)\??|"
    r"my (user )?id\??|"
    r"show (me )?my (profile|identity|account)"
    r")\s*$",
    re.IGNORECASE,
)

_MY_PERMISSIONS = re.compile(
    r"\b("
    r"what (are|is) my (permissions?|entitlements?|access|capabilities|roles?)|"
    r"what (permissions?|entitlements?|access|capabilities) do i have|"
    r"what can i do|"
    r"(list|show|summarize|summary of) my (permissions?|entitlements?|capabilities|roles?)|"
    r"my permissions\??"
    r")\b",
    re.IGNORECASE,
)

_USERS_LIKE_ME = re.compile(
    r"\b("
    r"other users like me|users like me|anyone like me|"
    r"peers like me|people like me|similar users to me|"
    r"who else (has|have|with) (the )?same (roles?|permissions?|access)"
    r")\b",
    re.IGNORECASE,
)

_CAN_I_APPROVE = re.compile(
    r"\b("
    r"do i (have permission|have the permission|have rights?) to approve|"
    r"can i approve|am i (allowed|able|permitted) to approve|"
    r"may i approve"
    r")\b",
    re.IGNORECASE,
)

_CAN_I_CREATE = re.compile(
    r"\b("
    r"do i (have permission|have the permission|have rights?) to create|"
    r"can i create|am i (allowed|able|permitted) to create|"
    r"may i create|"
    r"(permission|allowed) to create (a )?(payment|instruction)"
    r")\b",
    re.IGNORECASE,
)

_CAN_I_SUBMIT = re.compile(
    r"\b("
    r"do i (have permission|have the permission|have rights?) to submit|"
    r"can i submit|am i (allowed|able|permitted) to submit|"
    r"may i submit|"
    r"(permission|allowed) to submit (a )?payment"
    r")\b",
    re.IGNORECASE,
)

_WHO_ELSE_APPROVE = re.compile(
    r"\b("
    r"who else can approve|who besides me can approve|"
    r"who (else )?(can|could) (also )?approve"
    r")\b",
    re.IGNORECASE,
)

_WAITING_FOR_ME = re.compile(
    r"\b("
    r"waiting for my approval|pending my approval|"
    r"awaiting my approval|payments? (waiting|pending) for me|"
    r"any(thing)? waiting for my approval"
    r")\b",
    re.IGNORECASE,
)

_WHO_CAN_CREATE = re.compile(
    r"\b("
    r"who can create|"
    r"who (else )?(can|could) (create|draft)|"
    r"who (is|are) (able|allowed|permitted) to create|"
    r"which users? (can|may) create|"
    r"list .{0,40}(who can create|payment creators?|instruction creators?)|"
    r"who (can|may) draft"
    r")\b",
    re.IGNORECASE,
)


def _create_entity_type(message: str) -> Literal["payment", "instruction"] | None:
    lowered = message.lower()
    has_instruction = bool(re.search(r"\binstructions?\b", lowered))
    has_payment = bool(re.search(r"\bpayments?\b", lowered))
    if has_instruction and not has_payment:
        return "instruction"
    if has_payment and not has_instruction:
        return "payment"
    if has_payment and has_instruction:
        # Prefer the noun closest to "create" / "draft" when both appear.
        create_at = re.search(r"\b(create|draft)\b", lowered)
        if create_at:
            tail = lowered[create_at.start() :]
            instr_at = re.search(r"\binstructions?\b", tail)
            pay_at = re.search(r"\bpayments?\b", tail)
            if instr_at and (not pay_at or instr_at.start() < pay_at.start()):
                return "instruction"
            if pay_at:
                return "payment"
        return None
    return None


def detect_me_intent(message: str) -> MeIntent | None:
    """Detect me-centric operational intents from natural language."""
    text = message.strip()
    if not text:
        return None

    if _WHO_AM_I.match(text):
        return MeIntent(kind="who_am_i")

    payment_ids = extract_payment_ids(text) or extract_entity_ids(text)
    entity_id = payment_ids[0] if payment_ids else None

    if _WHO_CAN_CREATE.search(text):
        entity_type = _create_entity_type(text)
        if entity_type is not None:
            return MeIntent(
                kind="who_can_create",
                action="CREATE",
                entity_type=entity_type,
                covering_lob=lob_filter_from_question(text),
            )

    if _CAN_I_CREATE.search(text):
        entity_type = _create_entity_type(text) or "payment"
        return MeIntent(
            kind="can_act_on_entity",
            action="CREATE",
            entity_type=entity_type,
            entity_id=entity_id,
        )

    if _CAN_I_SUBMIT.search(text):
        return MeIntent(
            kind="can_act_on_entity",
            action="SUBMIT",
            entity_type="payment",
            entity_id=entity_id,
        )

    if _CAN_I_APPROVE.search(text):
        return MeIntent(
            kind="can_act_on_entity",
            action="APPROVE",
            entity_type="payment",
            entity_id=entity_id,
        )

    if _WHO_ELSE_APPROVE.search(text) and ("else" in text.lower() or "besides me" in text.lower()):
        return MeIntent(
            kind="who_else_can_act",
            action="APPROVE",
            entity_type="payment",
            entity_id=entity_id,
        )

    if _MY_PERMISSIONS.search(text):
        return MeIntent(kind="my_permissions")

    if _USERS_LIKE_ME.search(text):
        return MeIntent(kind="users_like_me")

    if _WAITING_FOR_ME.search(text):
        return MeIntent(kind="waiting_for_me", action="APPROVE", entity_type="payment")

    return None
