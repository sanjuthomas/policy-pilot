from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from regression.eval_metrics import (
    ROUTING_BY_RETRIEVAL,
    CaseQualityScores,
    entity_source_recall,
    evaluate_case_quality,
    faithfulness_proxy,
    graph_groundedness,
    source_channel_precision_at_k,
    summarize_suite_quality,
)
from regression.models import ExpectConfig, RegressionSuite

GOLDEN = Path(__file__).resolve().parents[1] / "regression" / "eval_golden.yaml"


def test_deterministic_routing_expectation():
    exp = ROUTING_BY_RETRIEVAL["deterministic"]
    assert "neo4j_direct" in exp.paths
    assert "deterministic" in exp.cypher_classes
    assert "formatter" in exp.synthesis_modes


def test_entity_source_recall_from_answer():
    recall = entity_source_recall(
        question="Who created payment 20260704-FICC-P-1?",
        answer="Payment 20260704-FICC-P-1 was created by alice.",
        sources=[],
        graph_rows=[],
    )
    assert recall == 1.0


def test_entity_source_recall_from_graph_row():
    recall = entity_source_recall(
        question="Status of instruction {id}",
        answer="It is approved.",
        sources=[],
        graph_rows=[{"instruction_id": "20260704-FICC-I-3", "status": "APPROVED"}],
        entity_ids=["20260704-FICC-I-3"],
    )
    assert recall == 1.0


def test_entity_source_recall_miss():
    recall = entity_source_recall(
        question="Who created payment 20260704-FICC-P-1?",
        answer="No matching payment found.",
        sources=[],
        graph_rows=[],
    )
    assert recall == 0.0


def test_source_channel_precision_at_k():
    sources = [
        {"sources": ["vector"], "summary": "alert denial"},
        {"sources": ["neo4j"], "summary": "graph only"},
    ]
    precision = source_channel_precision_at_k(
        sources,
        required_channels=frozenset({"vector"}),
        k=2,
    )
    assert precision == 0.5


def test_graph_groundedness_overlap():
    score = graph_groundedness(
        "User alice triggered 3 denial alerts this week.",
        [{"user": "alice", "count": 3, "category": "denial"}],
    )
    assert score is not None
    assert score > 0.2


def test_faithfulness_proxy():
    sources = [{"summary": "Policy denial by alice for payment submit", "sources": ["vector"]}]
    score = faithfulness_proxy(
        "Alice had a policy denial on payment submit.",
        sources=sources,
        graph_rows=[],
    )
    assert score is not None
    assert score > 0.1


def test_evaluate_case_quality_deterministic_pass():
    expect = ExpectConfig(require_routing=True, routing_path="neo4j_direct")
    scores = evaluate_case_quality(
        retrieval="deterministic",
        expect=expect,
        question="Who created payment 20260704-FICC-P-1?",
        answer="Payment 20260704-FICC-P-1 was created by bob.",
        sources=[],
        graph_rows=[{"creator": "bob", "payment_id": "20260704-FICC-P-1"}],
        routing={
            "path": "neo4j_direct",
            "cypher_provenance": "predefined_yaml",
            "answer_synthesis": "formatter",
        },
        generation_ms=12.0,
    )
    assert scores.routing_ok is True
    assert scores.passed


def test_evaluate_case_quality_routing_mismatch():
    scores = evaluate_case_quality(
        retrieval="deterministic",
        expect=ExpectConfig(require_routing=True),
        question="Count alerts",
        answer="3 alerts",
        sources=[],
        graph_rows=[],
        routing={
            "path": "full_rag",
            "cypher_provenance": "llm_graph_plan",
            "answer_synthesis": "gemini_full",
        },
        generation_ms=800.0,
    )
    assert not scores.passed
    assert any("routing path" in failure for failure in scores.failures)


def test_evaluate_case_quality_vector_requires_channels():
    scores = evaluate_case_quality(
        retrieval="vector",
        expect=ExpectConfig(require_routing=True),
        question="Summarize denials",
        answer="Several policy denials occurred involving payments and instructions.",
        sources=[{"sources": ["neo4j"], "summary": "graph hit"}],
        graph_rows=[],
        routing={"path": "full_rag", "answer_synthesis": "gemini_full"},
        generation_ms=400.0,
    )
    assert not scores.passed
    assert scores.source_precision_at_k == 0.0


def test_summarize_suite_quality():
    summary = summarize_suite_quality(
        [
            (
                "deterministic",
                CaseQualityScores(routing_ok=True, faithfulness=0.8, entity_recall=1.0),
            ),
            (
                "graph",
                CaseQualityScores(routing_ok=False, faithfulness=0.5, entity_recall=0.5),
            ),
        ]
    )
    assert summary.cases_scored == 2
    assert summary.routing_accuracy == 0.5
    assert summary.mean_faithfulness == 0.65
    assert summary.mean_entity_recall == 0.75


def test_golden_eval_yaml_loads():
    raw = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    suite = RegressionSuite.model_validate({"seed": {}, **raw})
    assert len(suite.cases) >= 26
    for case in suite.cases:
        assert case.expect.require_routing is True
    p0 = {c.id for c in suite.cases if "p0" in c.tags}
    assert "golden_instruction_denials_count_week" in p0
    assert "golden_payment_denials_count_today" in p0
    assert suite.seed.steps, "golden suite must carry the harness seed plan"
    by_id = {c.id: c for c in suite.cases}
    for case_id, intent in (
        ("golden_instruction_show_by_id_with_noun", "instruction.show_by_id"),
        ("golden_instruction_show_by_id_bare", "instruction.show_by_id"),
        ("golden_payment_show_by_id_with_noun", "payment.show_by_id"),
        ("golden_payment_show_by_id_bare", "payment.show_by_id"),
    ):
        case = by_id[case_id]
        assert case.expect.routing_path == "neo4j_direct"
        assert case.expect.intent_id == intent
        assert "regression_guard" in case.tags

    for case_id, retrieval, path in (
        ("golden_policies_eligible_approvers_payment", "eligibility", "eligibility"),
        ("golden_policies_eligible_submitters_payment", "eligibility", "eligibility"),
        ("golden_policies_eligible_approvers_instruction", "eligibility", "eligibility"),
        ("golden_policies_amount_club_directory", "policy_directory", "policy_directory"),
        ("golden_policies_covering_lob_directory", "policy_directory", "policy_directory"),
        (
            "golden_policies_instruction_approval_summary",
            "policy_summary",
            "policy_summary",
        ),
    ):
        case = by_id[case_id]
        assert case.mode == "policies"
        assert case.retrieval == retrieval
        assert case.expect.routing_path == path
        if case_id == "golden_policies_instruction_approval_summary":
            assert case.question == "What is the instruction approval policy?"
            assert case.expect.answer_synthesis == "eligibility_api"

    me_case = by_id["golden_me_who_am_i_identity_tokens_pay205"]
    assert me_case.persona == "pay-205"
    assert me_case.mode == "all"
    assert me_case.question == "Who am I?"
    assert me_case.expect.intent_id == "me.who_am_i"
    assert me_case.expect.answer_synthesis == "formatter"
    assert "`PAYMENT_CREATOR`" in me_case.expect.answer_contains_all
    assert "`UP_TO_1_BILLION_CLUB`" in me_case.expect.answer_contains_all
    assert "PAYMENTCREATOR" in me_case.expect.answer_not_contains
    assert "regression_guard" in me_case.tags

@pytest.mark.parametrize(
    "retrieval,path,synthesis,should_pass",
    [
        ("deterministic", "neo4j_direct", "formatter", True),
        ("graph", "neo4j_direct", "formatter", True),
        ("graph", "full_rag", "gemini_full", True),
    ],
)
def test_routing_path_acceptance(retrieval, path, synthesis, should_pass):
    sources = [{"sources": ["vector"], "summary": "denial alert event log"}]
    scores = evaluate_case_quality(
        retrieval=retrieval,
        expect=ExpectConfig(),
        question="Summarize",
        answer="Recent denial alerts were logged for multiple users in the system.",
        sources=sources if retrieval == "vector" else [],
        graph_rows=[{"count": 2}] if retrieval != "vector" else [],
        routing={
            "path": path,
            "cypher_provenance": "predefined_yaml" if path == "neo4j_direct" else "llm_graph_plan",
            "answer_synthesis": synthesis,
        },
        generation_ms=50.0 if path == "neo4j_direct" else 400.0,
    )
    assert scores.routing_ok is True
    assert scores.passed is should_pass


def test_vector_routing_fails_without_vector_sources():
    scores = evaluate_case_quality(
        retrieval="vector",
        expect=ExpectConfig(),
        question="Summarize denials",
        answer="Several policy denials occurred involving payments and instructions.",
        sources=[{"sources": ["neo4j"], "summary": "graph hit"}],
        graph_rows=[],
        routing={"path": "full_rag", "answer_synthesis": "gemini_full"},
        generation_ms=400.0,
    )
    assert scores.routing_ok is True
    assert not scores.passed
