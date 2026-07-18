from __future__ import annotations

from cypher_builder import is_payment_list_question, plan_graph_queries

from chat_application.graph.direct import match_neo4j_direct_intent
from chat_application.models import ChatMessage
from chat_application.pipeline.follow_up import expand_follow_up_question


def test_expand_list_those_payments_follow_up() -> None:
    history = [
        ChatMessage(
            role="user",
            content="How many payments did we create this week?",
        ),
        ChatMessage(
            role="assistant",
            content="There are 24 matching payment(s) for all LOBs (this week).",
        ),
    ]
    expanded = expand_follow_up_question("Can you list those payments?", history)
    assert "this week" in expanded.lower()
    assert "list" in expanded.lower()
    assert is_payment_list_question(expanded, mode="payments")
    planned = plan_graph_queries(expanded, mode="payments")
    assert planned is not None
    assert planned[0][0] == "payment_list"
    assert "P7D" in planned[0][1] or "duration" in planned[0][1]


def test_payment_list_created_this_week_direct() -> None:
    question = "List payments created this week"
    assert is_payment_list_question(question, mode="payments")
    planned = plan_graph_queries(question, mode="payments")
    assert planned is not None
    assert planned[0][0] == "payment_list"


def test_expand_noop_without_history() -> None:
    assert expand_follow_up_question("Can you list those payments?", []) == (
        "Can you list those payments?"
    )


def test_expand_noop_for_concrete_payment_id_lookup() -> None:
    """Regression: show-payment-by-id must not be rewritten to the prior list question."""
    history = [
        ChatMessage(
            role="user",
            content="are there any payments created using instruction 20260717-FICC-I-19?",
        ),
        ChatMessage(
            role="assistant",
            content="There are 2 payments in total for instruction 20260717-FICC-I-19.",
        ),
    ]
    message = "Can you show me payment 20260717-FICC-P-14?"
    assert expand_follow_up_question(message, history) == message


def test_expand_noop_for_concrete_instruction_id_lookup() -> None:
    history = [
        ChatMessage(
            role="user",
            content="How many payments did we create this week?",
        ),
        ChatMessage(role="assistant", content="There are 24 matching payment(s)."),
    ]
    message = "Can you show me the instruction 20260717-FICC-I-19?"
    assert expand_follow_up_question(message, history) == message


def test_expand_instruction_count_to_inventory_follow_up() -> None:
    history = [
        ChatMessage(
            role="user",
            content="How many approved instructions are there in the system?",
        ),
        ChatMessage(
            role="assistant",
            content="There are 11 approved instructions in the system.",
        ),
    ]

    expanded = expand_follow_up_question("Can you list those?", history)

    assert expanded.startswith("List the instructions matching the prior question:")
    assert "approved instructions" in expanded.lower()
    match = match_neo4j_direct_intent(expanded, mode="instructions")
    assert match is not None
    assert match.intent_id == "instruction.list_by_status"
    assert match.formatter_name == "instruction_inventory_table"
    assert "[:CURRENT]->" in match.planned[0][1]
    assert "status = 'APPROVED'" in match.planned[0][1]


def test_expand_noop_for_non_anaphoric_payment_request() -> None:
    history = [
        ChatMessage(
            role="user",
            content="How many payments did we create this week?",
        ),
        ChatMessage(role="assistant", content="There are 24 matching payments."),
    ]
    message = "Can you show payments awaiting approval?"

    assert expand_follow_up_question(message, history) == message

