from __future__ import annotations

import re
from typing import Literal

_ELIGIBILITY_PHRASES = (
    "who can approve",
    "who could approve",
    "who is eligible to approve",
    "who may approve",
    "eligible approvers",
    "eligible approver",
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

EligibleApproverTarget = Literal["payment", "instruction"]


def is_eligible_approver_question(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in _ELIGIBILITY_PHRASES)


def eligible_approver_target(message: str, *, mode: str) -> EligibleApproverTarget | None:
    """Resolve whether a live OPA eligibility question targets a payment or instruction."""
    if not is_eligible_approver_question(message):
        return None

    lowered = message.lower()
    mentions_payment = "payment" in lowered
    mentions_instruction = "instruction" in lowered or "ssi" in lowered

    if mentions_payment and not mentions_instruction:
        return "payment"
    if mentions_instruction and not mentions_payment:
        return "instruction"

    if mode == "instructions":
        return "instruction"
    if mode == "payments":
        return "payment"

    if mentions_payment:
        return "payment"
    if mentions_instruction:
        return "instruction"

    return None


def is_payment_eligible_approver_question(message: str, *, mode: str = "payments") -> bool:
    return eligible_approver_target(message, mode=mode) == "payment"


def is_instruction_eligible_approver_question(message: str, *, mode: str = "instructions") -> bool:
    return eligible_approver_target(message, mode=mode) == "instruction"
