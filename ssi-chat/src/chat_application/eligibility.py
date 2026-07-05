from __future__ import annotations

from typing import Literal

from chat_application.pipeline.heuristic_strategy import (
    is_eligibility_question_heuristic,
)
from chat_application.pipeline.heuristic_strategy import (
    resolve_eligibility_target as _resolve_eligibility_target,
)

EligibleApproverTarget = Literal["payment", "instruction"]


def is_eligible_approver_question(message: str) -> bool:
    """Heuristic eligibility detector — prefer LLM routing in production."""
    return is_eligibility_question_heuristic(message)


def eligible_approver_target(message: str, *, mode: str) -> EligibleApproverTarget | None:
    if not is_eligible_approver_question(message):
        return None
    return _resolve_eligibility_target(message, mode=mode)


def is_payment_eligible_approver_question(message: str, *, mode: str = "payments") -> bool:
    return eligible_approver_target(message, mode=mode) == "payment"


def is_instruction_eligible_approver_question(message: str, *, mode: str = "instructions") -> bool:
    return eligible_approver_target(message, mode=mode) == "instruction"
