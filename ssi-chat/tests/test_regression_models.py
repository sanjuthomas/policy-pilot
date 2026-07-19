from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from regression.assertions import evaluate_confirm_expectations, evaluate_expectations
from regression.models import (
    SKILL_CONFIRM_PATHS,
    ConfirmStep,
    ExpectConfig,
    RegressionCase,
    RegressionSuite,
)

QUESTIONS = Path(__file__).resolve().parents[1] / "regression" / "questions.yaml"


def load_suite() -> RegressionSuite:
    raw = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    return RegressionSuite.model_validate(raw)


def test_regression_cases_have_unique_ids():
    suite = load_suite()
    ids = [case.id for case in suite.cases]
    assert len(ids) == len(set(ids)), f"duplicate case ids: {ids}"


def test_regression_cases_all_have_retrieval():
    suite = load_suite()
    assert len(suite.cases) >= 63
    for case in suite.cases:
        assert case.retrieval in {
            "deterministic",
            "graph",
            "vector",
            "eligibility",
            "policy_directory",
            "skill",
        }


def test_regression_retrieval_distribution():
    suite = load_suite()
    counts = Counter(case.retrieval for case in suite.cases)
    assert counts["deterministic"] == 28
    assert counts["graph"] == 31
    assert counts["vector"] == 3
    assert counts["eligibility"] == 2
    assert counts["policy_directory"] == 2
    assert counts["skill"] == 8


def test_regression_policies_mode_cases_present():
    suite = load_suite()
    by_id = {case.id: case for case in suite.cases}
    payment = by_id["policies_eligible_approvers_payment"]
    instruction = by_id["policies_eligible_approvers_instruction"]
    amount = by_id["policies_amount_club_directory"]
    covering = by_id["policies_covering_lob_directory"]

    assert payment.mode == "policies"
    assert payment.retrieval == "eligibility"
    assert payment.expect.routing_path == "eligibility"
    assert "submitted_payment_id" in payment.expect.requires_context

    assert instruction.mode == "policies"
    assert instruction.retrieval == "eligibility"
    assert "pending_instruction_id" in instruction.expect.requires_context

    assert amount.mode == "policies"
    assert amount.retrieval == "policy_directory"
    assert amount.expect.routing_path == "policy_directory"

    assert covering.mode == "policies"
    assert covering.retrieval == "policy_directory"
    assert covering.expect.routing_path == "policy_directory"


def test_regression_show_by_id_bare_parity_cases():
    """Guard: bare `show me <id>` must stay on the same neo4j_direct intent as with noun."""
    suite = load_suite()
    by_id = {case.id: case for case in suite.cases}
    for case_id, intent in (
        ("instructions_show_by_id_with_noun", "instruction.show_by_id"),
        ("instructions_show_by_id_bare", "instruction.show_by_id"),
        ("payments_show_by_id_with_noun", "payment.show_by_id"),
        ("payments_show_by_id_bare", "payment.show_by_id"),
    ):
        case = by_id[case_id]
        assert case.retrieval == "deterministic"
        assert case.expect.require_routing is True
        assert case.expect.routing_path == "neo4j_direct"
        assert case.expect.intent_id == intent
        assert case.expect.answer_synthesis == "formatter"


def test_regression_seed_leaves_draft_for_submit_skill():
    suite = load_suite()
    create = next(s for s in suite.seed.steps if s.action == "create-payments")
    submit = next(s for s in suite.seed.steps if s.action == "submit-payments")
    assert (create.count or 0) > (submit.count or 0)


def test_regression_skill_cases_present():
    suite = load_suite()
    by_id = {case.id: case for case in suite.cases}
    create = by_id["skill_create_payment_phase1_nogo"]
    submit = by_id["skill_submit_payment_phase1_nogo"]
    approve = by_id["skill_approve_payment_phase1_nogo"]
    cancel = by_id["skill_cancel_payment_phase1_nogo"]
    create_denied = by_id["skill_create_payment_forbidden"]
    submit_denied = by_id["skill_submit_payment_forbidden"]
    approve_denied = by_id["skill_approve_payment_forbidden"]
    cancel_denied = by_id["skill_cancel_payment_forbidden"]

    assert create.persona == "pay-101"
    assert create.confirm is not None and create.confirm.decision == "no_go"
    assert create.expect.skill_name == "create_payment"

    assert submit.persona == "fo-ficc-101"
    assert submit.expect.skill_name == "submit_payment"
    assert "draft_payment_id" in submit.expect.requires_context

    assert approve.persona == "pay-400"
    assert approve.expect.skill_name == "approve_payment"
    assert "submitted_payment_id" in approve.expect.requires_context

    assert cancel.persona == "pay-101"
    assert cancel.expect.skill_name == "cancel_payment"
    assert "draft_payment_id" in cancel.expect.requires_context
    assert cancel.confirm is not None
    assert cancel.confirm.intent_id == "skill.cancel_payment.no_go"

    assert create_denied.persona == "pay-400"
    assert create_denied.expect.forbid_skill_confirmation
    assert create_denied.expect.intent_id == "skill.create_payment.forbidden"

    assert submit_denied.persona == "pay-400"
    assert submit_denied.expect.forbid_skill_confirmation
    assert submit_denied.expect.intent_id == "skill.submit_payment.forbidden"

    assert approve_denied.persona == "fo-ficc-101"
    assert approve_denied.expect.forbid_skill_confirmation
    assert approve_denied.expect.intent_id == "skill.approve_payment.forbidden"

    assert cancel_denied.persona == "fo-ficc-101"
    assert cancel_denied.expect.forbid_skill_confirmation
    assert cancel_denied.expect.intent_id == "skill.cancel_payment.forbidden"


def test_regression_alert_entity_id_case_present():
    suite = load_suite()
    case = next(c for c in suite.cases if c.id == "events_alerts_list_today_entity_ids")
    assert case.retrieval == "deterministic"
    assert "Entity ID" in case.expect.answer_contains_all
    assert any("-I-" in token or "-P-" in token for token in case.expect.answer_contains_any)


def test_regression_case_model_accepts_retrieval():
    case = RegressionCase.model_validate(
        {
            "id": "example",
            "mode": "events",
            "retrieval": "vector",
            "question": "Show alerts today",
        }
    )
    assert case.retrieval == "vector"


def test_regression_case_model_accepts_skill_persona_confirm():
    case = RegressionCase.model_validate(
        {
            "id": "skill_example",
            "mode": "payments",
            "retrieval": "skill",
            "persona": "pay-400",
            "question": "Please approve payment {submitted_payment_id}.",
            "confirm": {"decision": "no_go", "intent_id": "skill.approve_payment.cancelled"},
            "expect": {
                "require_skill_confirmation": True,
                "skill_name": "approve_payment",
                "intent_id": "skill.approve_payment.awaiting_confirmation",
            },
        }
    )
    assert case.retrieval == "skill"
    assert case.persona == "pay-400"
    assert case.confirm is not None
    assert case.confirm.decision == "no_go"
    assert SKILL_CONFIRM_PATHS["approve_payment"].endswith("/approve-payment/confirm")
    assert SKILL_CONFIRM_PATHS["cancel_payment"].endswith("/cancel-payment/confirm")


def test_evaluate_skill_confirmation_expectations():
    ok, reason = evaluate_expectations(
        ExpectConfig(
            intent_id="skill.create_payment.awaiting_confirmation",
            require_skill_confirmation=True,
            skill_name="create_payment",
            min_answer_length=5,
            answer_contains_all=["Preflight"],
        ),
        answer="Preflight passed. Choose **Go** or **No Go**.",
        sources=[],
        graph_rows=[],
        cypher=None,
        intent_id="skill.create_payment.awaiting_confirmation",
        skill_confirmation={"pending_id": "abc", "skill": "create_payment", "card": {}},
    )
    assert ok, reason


def test_evaluate_forbid_skill_confirmation_expectations():
    ok, reason = evaluate_expectations(
        ExpectConfig(
            intent_id="skill.approve_payment.forbidden",
            forbid_skill_confirmation=True,
            min_answer_length=5,
            answer_contains_all=["cannot run"],
        ),
        answer="No Go from preflight — cannot run approve-payment skill.",
        sources=[],
        graph_rows=[],
        cypher=None,
        intent_id="skill.approve_payment.forbidden",
        skill_confirmation=None,
    )
    assert ok, reason

    ok, reason = evaluate_expectations(
        ExpectConfig(forbid_skill_confirmation=True),
        answer="Unexpected confirmation.",
        sources=[],
        graph_rows=[],
        cypher=None,
        skill_confirmation={"pending_id": "abc", "skill": "approve_payment"},
    )
    assert not ok
    assert reason == "did not expect skill_confirmation"


def test_evaluate_confirm_no_go():
    ok, reason = evaluate_confirm_expectations(
        ConfirmStep(
            decision="no_go",
            intent_id="skill.create_payment.cancelled",
            answer_contains_any=["cancelled"],
        ),
        answer="**No Go** — cancelled. No payment was created.",
        intent_id="skill.create_payment.cancelled",
    )
    assert ok, reason
