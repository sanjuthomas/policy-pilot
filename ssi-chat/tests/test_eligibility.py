from chat_application.pipeline.heuristic_strategy import (
    is_eligibility_question_heuristic,
    resolve_eligibility_target,
)

INSTRUCTION_ID = "11111111-1111-1111-1111-111111111111"


def _eligible_approver_target(message: str, *, mode: str) -> str | None:
    if not is_eligibility_question_heuristic(message):
        return None
    return resolve_eligibility_target(message, mode=mode)


def test_instruction_mode_routes_instruction_eligibility_question() -> None:
    q = f"Who can approve this instruction {INSTRUCTION_ID}?"
    assert _eligible_approver_target(q, mode="instructions") == "instruction"


def test_instruction_mode_does_not_route_to_payment_without_payment_word() -> None:
    q = f"Who can approve {INSTRUCTION_ID}?"
    assert _eligible_approver_target(q, mode="instructions") == "instruction"


def test_payment_mode_routes_payment_eligibility_question() -> None:
    q = f"Who can approve payment {INSTRUCTION_ID}?"
    assert _eligible_approver_target(q, mode="payments") == "payment"


def test_ignores_unrelated_questions() -> None:
    assert (
        _eligible_approver_target(
            "How many payments were approved today?", mode="payments"
        )
        is None
    )


def test_events_mode_resolves_ambiguous_payment_mention() -> None:
    q = "Who can approve payment for this instruction?"
    assert _eligible_approver_target(q, mode="events") == "payment"


def test_events_mode_resolves_ambiguous_instruction_mention() -> None:
    q = "Who can approve this instruction?"
    assert _eligible_approver_target(q, mode="events") == "instruction"
