"""Tests for etl.graph_model action → edge mappings."""

from __future__ import annotations

from etl.graph_model import (
    INSTRUCTION_ACTION_TO_EDGE,
    PAYMENT_ACTION_TO_EDGE,
    instruction_lifecycle_actor,
    is_version_open,
    payment_lifecycle_actor,
    release_use_payment_id,
)


def test_is_version_open():
    assert is_version_open("9999-12-31T23:59:59Z") is True
    assert is_version_open(None) is True
    assert is_version_open("2026-01-01T00:00:00Z") is False


def test_instruction_action_mapping():
    assert INSTRUCTION_ACTION_TO_EDGE["USE"] == "USED_IV"
    assert INSTRUCTION_ACTION_TO_EDGE["RELEASE_USE"] == "RELEASED_IV"


def test_payment_action_mapping():
    assert PAYMENT_ACTION_TO_EDGE["SUBMIT"] == "SUBMITTED_PV"
    assert PAYMENT_ACTION_TO_EDGE["SUBMIT_PAYMENT"] == "SUBMITTED_PV"


def test_payment_lifecycle_actor_submit():
    fact = {
        "action": "SUBMIT",
        "submitted_by": {"user_id": "fo-200", "given_name": "A", "family_name": "B"},
    }
    assert payment_lifecycle_actor(fact) == "fo-200"


def test_instruction_use_actor_props():
    fact = {
        "action": "USE",
        "actor_user_id": "fo-101",
        "instruction_snapshot": {
            "used_by": "pay-001",
            "lifecycle_events": [
                {
                    "action": "USE",
                    "actor_user_id": "fo-101",
                    "details": {"payment_reference": "pay-001", "delegated_by": "svc-payment"},
                }
            ],
        },
    }
    user_id, props = instruction_lifecycle_actor(fact)
    assert user_id == "fo-101"
    assert props["payment_id"] == "pay-001"
    assert props["delegated_by"] == "svc-payment"


def test_release_use_payment_id():
    fact = {
        "action": "RELEASE_USE",
        "instruction_snapshot": {
            "lifecycle_events": [
                {"action": "RELEASE_USE", "details": {"payment_reference": "pay-99"}},
            ],
        },
    }
    assert release_use_payment_id(fact) == "pay-99"


def test_payment_lifecycle_actor_submit_legacy():
    fact = {
        "action": "SUBMIT_PAYMENT",
        "submitted_by": {"user_id": "fo-200", "given_name": "A", "family_name": "B"},
    }
    assert payment_lifecycle_actor(fact) == "fo-200"
