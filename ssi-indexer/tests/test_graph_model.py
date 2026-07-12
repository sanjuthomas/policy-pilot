"""Tests for etl.graph_model action → edge mappings."""

from __future__ import annotations

import pytest
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


@pytest.mark.parametrize(
    ("action", "snapshot_field", "expected_user"),
    [
        ("CREATE", "created_by", "creator"),
        ("SUBMIT", "submitted_by", "submitter"),
        ("APPROVE", "approved_by", "approver"),
        ("REJECT", "rejected_by", "rejector"),
        ("CANCEL", "cancelled_by", "canceller"),
    ],
)
def test_instruction_lifecycle_actor_snapshot_actions(
    action: str, snapshot_field: str, expected_user: str
) -> None:
    user_id, props = instruction_lifecycle_actor(
        {
            "action": action,
            "instruction_snapshot": {snapshot_field: {"user_id": expected_user}},
        }
    )

    assert user_id == expected_user
    assert props == {}


@pytest.mark.parametrize("action", ["SUSPEND", "REACTIVATE", "RELEASE_USE"])
def test_instruction_lifecycle_actor_direct_actions(action: str) -> None:
    assert instruction_lifecycle_actor({"action": action, "actor_user_id": "operator"}) == (
        "operator",
        {},
    )


def test_instruction_lifecycle_actor_handles_empty_lifecycle_details() -> None:
    assert instruction_lifecycle_actor({"action": "USE", "instruction_snapshot": {}}) == (
        None,
        {},
    )
    assert instruction_lifecycle_actor({"action": "UNKNOWN"}) == (None, {})


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


@pytest.mark.parametrize(
    ("action", "field"),
    [
        ("CREATE", "created_by"),
        ("APPROVE", "approved_by"),
        ("REJECT", "rejected_by"),
        ("CANCEL", "cancelled_by"),
    ],
)
def test_payment_lifecycle_actor_snapshot_actions(action: str, field: str) -> None:
    assert payment_lifecycle_actor(
        {"action": action, field: {"user_id": "actor"}}
    ) == "actor"


def test_payment_lifecycle_actor_falls_back_to_actor_user_id() -> None:
    assert payment_lifecycle_actor({"action": "UNKNOWN", "actor_user_id": "actor"}) == "actor"
