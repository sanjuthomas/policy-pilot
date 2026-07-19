"""Tests for subject LOB Cypher scope helpers."""

from __future__ import annotations

from cypher_builder.lob_scope import owning_lob_and_clause, retrieval_lob_scope
from cypher_builder.query_engine import plan_graph_queries


def test_outside_scope_question_lob_only() -> None:
    assert owning_lob_and_clause(alias="p", question="payments for FICC") == (
        " AND p.owning_lob = 'FICC'"
    )
    assert owning_lob_and_clause(alias="p", question="how many payments?") == ""


def test_compliance_unscoped_still_honors_question_lob() -> None:
    with retrieval_lob_scope(None):
        assert owning_lob_and_clause(alias="e", question="FICC alerts") == (
            " AND e.owning_lob = 'FICC'"
        )
        assert owning_lob_and_clause(alias="e") == ""


def test_fo_scope_injects_in_clause() -> None:
    with retrieval_lob_scope(frozenset({"FICC"})):
        assert owning_lob_and_clause(alias="p") == " AND p.owning_lob = 'FICC'"
        assert "AND false" in owning_lob_and_clause(
            alias="p", question="payments for FX"
        )


def test_mo_multi_covering_uses_in_list() -> None:
    with retrieval_lob_scope(frozenset({"FICC", "FX"})):
        clause = owning_lob_and_clause(alias="v")
        assert "IN [" in clause
        assert "'FICC'" in clause
        assert "'FX'" in clause


def test_empty_allowed_denies() -> None:
    with retrieval_lob_scope(frozenset()):
        assert owning_lob_and_clause(alias="e") == " AND false"


def test_plan_graph_alert_count_scoped() -> None:
    with retrieval_lob_scope(frozenset({"FX"})):
        planned = plan_graph_queries(
            "How many instruction policy denials happened this week?",
            mode="events",
        )
    assert planned
    cypher = planned[0][1]
    assert "e.owning_lob = 'FX'" in cypher or "e.owning_lob IN" in cypher
