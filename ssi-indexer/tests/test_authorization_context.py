"""Tests for etl.authorization_context."""

from __future__ import annotations

import json

from etl.authorization_context import (
    authorization_fact_neo4j_params,
    authorization_from_event,
    authorization_from_fact,
    authorization_merged_fields,
    authorization_merged_from_fact,
    authorization_neo4j_params,
    authorization_search_parts,
)


def test_authorization_from_event_with_valid_auth():
    event = {"details": {"authorization": {"decision": "ALLOW", "summary": "ok"}}}
    assert authorization_from_event(event) == {"decision": "ALLOW", "summary": "ok"}


def test_authorization_from_event_missing_or_invalid():
    assert authorization_from_event({}) == {}
    assert authorization_from_event({"details": {}}) == {}
    assert authorization_from_event({"details": {"authorization": "bad"}}) == {}


def test_authorization_merged_fields_full():
    event = {
        "timestamp": "2024-01-01T00:00:00Z",
        "actor": {"groups": ["ops"], "covering_lobs": ["LOB1"]},
        "event": {"reason": "event reason"},
        "details": {
            "authorization": {
                "summary": "auth summary",
                "decision": "DENY",
                "allow_basis": ["rule-a"],
                "violations": ["v1"],
                "is_alert": True,
                "subject_at_decision": {"groups": ["subj"], "covering_lobs": ["LOB2"]},
            }
        },
    }
    merged = authorization_merged_fields(event)
    assert merged["timestamp"] == "2024-01-01T00:00:00Z"
    assert merged["authorization_summary"] == "auth summary"
    assert merged["authorization_decision"] == "DENY"
    assert merged["authorization_basis"] == ["rule-a"]
    assert merged["authorization_violations"] == ["v1"]
    assert merged["authorization_is_alert"] is True
    assert merged["event_reason"] == "event reason"
    assert merged["actor_groups"] == ["ops"]
    assert merged["actor_covering_lobs"] == ["LOB1"]


def test_authorization_merged_fields_fallbacks():
    event = {
        "event": {"reason": "fallback reason"},
        "details": {"authorization": {}},
    }
    merged = authorization_merged_fields(event)
    assert merged["authorization_summary"] == "fallback reason"
    assert merged["actor_groups"] == []
    assert merged["actor_covering_lobs"] == []


def test_authorization_merged_fields_subject_fallback():
    event = {
        "details": {
            "authorization": {
                "subject_at_decision": {
                    "groups": ["from-subject"],
                    "covering_lobs": ["LOB-S"],
                }
            }
        }
    }
    merged = authorization_merged_fields(event)
    assert merged["actor_groups"] == ["from-subject"]
    assert merged["actor_covering_lobs"] == ["LOB-S"]


def test_authorization_search_parts():
    merged = {
        "timestamp": "t1",
        "authorization_summary": "sum",
        "authorization_decision": "ALLOW",
        "event_reason": "reason",
        "authorization_basis": ["a", "b"],
        "authorization_violations": ["v"],
        "actor_groups": ["g1"],
        "actor_covering_lobs": ["lob"],
    }
    parts = authorization_search_parts(merged)
    assert parts == [
        "t1",
        "sum",
        "ALLOW",
        "reason",
        "a b",
        "v",
        "g1",
        "lob",
    ]


def test_authorization_search_parts_skips_empty():
    assert authorization_search_parts({}) == []


def test_authorization_neo4j_params():
    event = {
        "details": {
            "authorization": {
                "summary": "s",
                "decision": "ALLOW",
                "allow_basis": ["x"],
                "violations": ["y"],
            }
        }
    }
    params = authorization_neo4j_params(event)
    assert params["authorization_summary"] == "s"
    assert params["authorization_decision"] == "ALLOW"
    assert json.loads(params["authorization_basis"]) == ["x"]
    assert json.loads(params["authorization_violations"]) == ["y"]


def test_authorization_from_fact():
    assert authorization_from_fact({"authorization": {"decision": "X"}}) == {"decision": "X"}
    assert authorization_from_fact({}) == {}
    assert authorization_from_fact({"authorization": None}) == {}


def test_authorization_merged_from_fact():
    fact = {
        "authorization": {
            "summary": "approved",
            "decision": "ALLOW",
            "allow_basis": ["basis"],
            "violations": [],
            "is_alert": False,
        },
        "instruction_snapshot": {
            "approved_at": "2024-02-01",
            "rejected_at": None,
            "submitted_at": "2024-01-15",
            "rejection_reason": None,
        },
    }
    merged = authorization_merged_from_fact(fact)
    assert merged["approved_at"] == "2024-02-01"
    assert merged["authorization_summary"] == "approved"
    assert merged["authorization_basis"] == ["basis"]


def test_authorization_fact_neo4j_params():
    fact = {
        "authorization": {"summary": "ok", "allow_basis": ["r1"]},
        "instruction_snapshot": {
            "approved_at": "2024-03-01",
            "submitted_at": "2024-02-28",
            "rejected_at": None,
        },
    }
    params = authorization_fact_neo4j_params(fact)
    assert params["approved_at"] == "2024-03-01"
    assert params["submitted_at"] == "2024-02-28"
    assert params["authorization_summary"] == "ok"
    assert json.loads(params["authorization_basis"]) == ["r1"]


def test_authorization_fact_neo4j_params_empty_basis_is_none():
    fact = {"authorization": None, "instruction_snapshot": {"approved_at": "2024-03-01"}}
    params = authorization_fact_neo4j_params(fact)
    assert params["authorization_summary"] is None
    assert params["authorization_basis"] is None
