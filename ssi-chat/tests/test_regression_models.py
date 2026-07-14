from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml
from regression.models import RegressionCase, RegressionSuite

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
    assert len(suite.cases) >= 56
    for case in suite.cases:
        assert case.retrieval in {"deterministic", "graph", "vector", "eligibility"}


def test_regression_retrieval_distribution():
    suite = load_suite()
    counts = Counter(case.retrieval for case in suite.cases)
    assert counts["deterministic"] == 23
    assert counts["graph"] == 30
    assert counts["vector"] == 3
    assert counts.get("eligibility", 0) == 0


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
