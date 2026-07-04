from chat_application.eligibility import (
    eligible_approver_target,
    is_instruction_eligible_approver_question,
    is_payment_eligible_approver_question,
)

INSTRUCTION_ID = "11111111-1111-1111-1111-111111111111"


def test_instruction_mode_routes_instruction_eligibility_question() -> None:
    q = f"Who can approve this instruction {INSTRUCTION_ID}?"
    assert eligible_approver_target(q, mode="instructions") == "instruction"
    assert is_instruction_eligible_approver_question(q, mode="instructions")


def test_instruction_mode_does_not_route_to_payment_without_payment_word() -> None:
    q = f"Who can approve {INSTRUCTION_ID}?"
    assert eligible_approver_target(q, mode="instructions") == "instruction"
    assert not is_payment_eligible_approver_question(q, mode="instructions")


def test_payment_mode_routes_payment_eligibility_question() -> None:
    q = f"Who can approve payment {INSTRUCTION_ID}?"
    assert eligible_approver_target(q, mode="payments") == "payment"
    assert is_payment_eligible_approver_question(q, mode="payments")


def test_ignores_unrelated_questions() -> None:
    assert eligible_approver_target("How many payments were approved today?", mode="payments") is None


def test_events_mode_resolves_ambiguous_payment_mention() -> None:
    q = "Who can approve payment for this instruction?"
    assert eligible_approver_target(q, mode="events") == "payment"


def test_events_mode_resolves_ambiguous_instruction_mention() -> None:
    q = "Who can approve this instruction?"
    assert eligible_approver_target(q, mode="events") == "instruction"
