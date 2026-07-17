from __future__ import annotations

from unittest.mock import patch

import pytest
from chat_application.observability.skills import (
    parse_skill_intent,
    record_skill_outcome,
)


@pytest.mark.parametrize(
    ("intent_id", "expected"),
    [
        ("skill.cancel_payment.cancelled", ("cancel_payment", "cancelled", "ok")),
        ("skill.create_payment.denied", ("create_payment", "denied", "ok")),
        ("skill.approve_payment.awaiting_confirmation", ("approve_payment", "awaiting_confirmation", "ok")),
        ("skill.submit_payment.wrong_status", ("submit_payment", "wrong_status", "ok")),
        ("skill.cancel_payment.cancel_error", ("cancel_payment", "cancel_error", "error")),
        ("skill.create_payment.evaluate_error", ("create_payment", "evaluate_error", "error")),
        ("skill.create_payment.auth_error", ("create_payment", "auth_error", "error")),
        ("skill", ("unknown", "unknown", "ok")),
        ("skill.cancel_payment", ("cancel_payment", "unknown", "ok")),
    ],
)
def test_parse_skill_intent(intent_id: str, expected: tuple[str, str, str]) -> None:
    assert parse_skill_intent(intent_id) == expected


@pytest.mark.parametrize("intent_id", [None, "", "me.can_act_on_entity", "graph.lookup"])
def test_parse_skill_intent_non_skill(intent_id: str | None) -> None:
    assert parse_skill_intent(intent_id) is None


def test_record_skill_outcome_records_counter() -> None:
    with patch("chat_application.observability.skills.record_counter") as record:
        record_skill_outcome("skill.cancel_payment.cancelled")

    record.assert_called_once()
    attrs = record.call_args.kwargs["attributes"]
    assert attrs == {
        "chat.skill": "cancel_payment",
        "chat.skill.outcome": "cancelled",
        "chat.skill.status": "ok",
    }


def test_record_skill_outcome_skips_non_skill_intent() -> None:
    with patch("chat_application.observability.skills.record_counter") as record:
        record_skill_outcome("me.can_act_on_entity")
        record_skill_outcome(None)

    record.assert_not_called()


def test_record_skill_outcome_no_telemetry_is_noop() -> None:
    # Telemetry is not configured under pytest; must not raise.
    record_skill_outcome("skill.create_payment.created")
