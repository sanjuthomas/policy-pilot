from __future__ import annotations

import random
from pathlib import Path

from harness.fixtures import load_users
from harness.helpers import (
    _approver_for_payment,
    _eligible_payment_approvers,
    build_payment_seed_plan,
)


def _users_file() -> Path:
    return Path(__file__).resolve().parents[2] / "zitadel-seed" / "users.yaml"


def test_eligible_payment_approvers_exclude_creator_and_subordinates() -> None:
    seed = load_users(_users_file())

    eligible = _eligible_payment_approvers(
        seed,
        owning_lob="FICC",
        amount=1_000_000.0,
        creator_user_id="pay-101",
        creator_supervisor_id="pay-201",
    )

    assert "pay-101" not in eligible
    assert eligible
    assert all(user_id != "pay-101" for user_id in eligible)


def test_approver_for_payment_randomizes_within_eligible_set() -> None:
    seed = load_users(_users_file())
    payment = {
        "owning_lob": "FICC",
        "amount": 1_000_000.0,
        "created_by": {"user_id": "pay-101", "supervisor_id": "pay-201"},
    }

    first = {
        _approver_for_payment(seed, payment, rng=random.Random(1))
        for _ in range(8)
    }
    second = {
        _approver_for_payment(seed, payment, rng=random.Random(2))
        for _ in range(8)
    }

    assert first
    assert second
    assert first != second or len(first) == 1


def test_build_payment_seed_plan_randomizes_creators_and_amounts() -> None:
    seed = load_users(_users_file())
    rng = random.Random(42)

    plan = build_payment_seed_plan(10, seed=seed, rng=rng)
    creators = {row[0] for row in plan}
    amounts = {row[1] for row in plan}

    assert len(plan) == 10
    assert creators <= {"pay-101", "pay-102", "pay-103", "pay-203", "pay-205", "pay-300"}
    assert len(amounts) > 1

    other = build_payment_seed_plan(10, seed=seed, rng=random.Random(99))
    assert plan != other
