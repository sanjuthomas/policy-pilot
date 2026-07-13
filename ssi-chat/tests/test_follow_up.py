from __future__ import annotations

from chat_application.models import ChatMessage
from chat_application.pipeline.follow_up import expand_follow_up_question
from cypher_builder import is_payment_list_question, plan_graph_queries


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
