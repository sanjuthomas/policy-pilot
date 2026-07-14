"""Paired Neo4j-direct vs full-RAG formatter parity (issue #12)."""

from __future__ import annotations

from typing import Any

import pytest

from chat_application.formatting.dispatch import format_planned_graph_answer
from chat_application.formatting.response import format_chat_response
from chat_application.graph.cypher import plan_graph_queries
from chat_application.graph.direct import (
    format_neo4j_direct_answer,
    match_planned_graph_intent,
)
from chat_application.models import SearchMode

# question, mode, sample rows — same rows must format identically on both paths
_PARITY_CASES: list[tuple[str, SearchMode, list[dict[str, Any]]]] = [
    (
        "How many single use instructions are there?",
        "instructions",
        [{"total": 2}],
    ),
    (
        "How many payments do we have?",
        "payments",
        [{"total": 5}],
    ),
    (
        "How many payments were approved today for FICC?",
        "payments",
        [{"total": 3}],
    ),
    (
        "Can you group instructions by status?",
        "instructions",
        [{"status": "APPROVED", "total": 4}, {"status": "DRAFT", "total": 1}],
    ),
    (
        "What is the largest payment?",
        "payments",
        [
            {
                "payment_id": "20260704-FICC-P-1",
                "amount": 1_000_000.0,
                "currency": "USD",
                "status": "APPROVED",
            }
        ],
    ),
    (
        "List payments above 100000",
        "payments",
        [
            {
                "payment_id": "20260704-FICC-P-1",
                "amount": 250_000.0,
                "currency": "USD",
                "status": "APPROVED",
            }
        ],
    ),
]


@pytest.mark.parametrize("question,mode,rows", _PARITY_CASES)
def test_planned_formatter_parity_direct_and_synthesize_paths(
    question: str,
    mode: SearchMode,
    rows: list[dict[str, Any]],
) -> None:
    planned = plan_graph_queries(question, mode=mode)
    assert planned is not None, f"expected a graph plan for {question!r}"

    shared = format_planned_graph_answer(
        question, mode=mode, planned=planned, rows=rows
    )
    assert shared is not None

    match = match_planned_graph_intent(question, mode=mode)
    assert match is not None
    direct = format_neo4j_direct_answer(match, question, rows, mode=mode)
    assert direct == shared

    # Synthesize wraps with format_chat_response; core text must match.
    assert format_chat_response(shared) == format_chat_response(direct)


def test_instruction_count_uses_instruction_wording_not_payment() -> None:
    question = "How many single use instructions are there?"
    planned = plan_graph_queries(question, mode="instructions")
    assert planned is not None
    answer = format_planned_graph_answer(
        question, mode="instructions", planned=planned, rows=[{"total": 2}]
    )
    assert answer is not None
    assert "instruction" in answer.lower()
    assert "payment" not in answer.lower()


def test_payment_count_label_formats_on_direct_path() -> None:
    question = "How many payments do we have?"
    planned = plan_graph_queries(question, mode="payments")
    assert planned is not None
    assert planned[0][0] == "payment_count"
    answer = format_planned_graph_answer(
        question, mode="payments", planned=planned, rows=[{"total": 5}]
    )
    assert answer is not None
    assert "5" in answer
    assert "payment" in answer.lower()


def test_instruction_inventory_label_formats_without_phrase_match() -> None:
    """LLM graph plans attach instruction_inventory even when wording misses direct YAML."""
    question = "Can you show me the single use instructions in the system?"
    planned = [("instruction_inventory", "MATCH (i:Instruction) RETURN i LIMIT 1")]
    rows = [
        {
            "instruction_id": "20260714-FICC-I-1",
            "status": "APPROVED",
            "owning_lob": "FICC",
            "currency": "USD",
            "creator_display": "Chen, Sarah (mo-100)",
            "approver_display": "Vasquez, Elena (ficc-300)",
        }
    ]
    answer = format_planned_graph_answer(
        question, mode="instructions", planned=planned, rows=rows
    )
    assert answer is not None
    assert "20260714-FICC-I-1" in answer
    assert "|" in answer  # markdown table
    assert "Instruction ID" in answer
