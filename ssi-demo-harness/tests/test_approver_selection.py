from __future__ import annotations

import random

from harness.fixtures import load_users_from_yaml as load_users
from harness.helpers import (
    _approver_for_instruction,
    _eligible_instruction_approvers,
    build_seed_plan,
)


def test_eligible_approvers_respect_reporting_lines() -> None:
    seed = load_users(__import__("pathlib").Path(__file__).resolve().parents[2] / "zitadel-seed" / "users.yaml")

    eligible = _eligible_instruction_approvers(
        seed,
        owning_lob="FICC",
        creator_user_id="mo-100",
        creator_title="Analyst",
        creator_supervisor_id="mo-050",
    )

    assert "ficc-300" in eligible
    assert "mo-050" not in eligible
    assert "mo-100" not in eligible


def test_mo_050_ficc_instruction_has_senior_approver() -> None:
    seed = load_users(__import__("pathlib").Path(__file__).resolve().parents[2] / "zitadel-seed" / "users.yaml")

    approver = _approver_for_instruction(
        seed,
        "FICC",
        "mo-050",
        "Vice President",
        "mo-010",
        rng=random.Random(0),
    )

    assert approver in {"ficc-400", "ficc-500"}


def test_build_seed_plan_randomizes_with_valid_pairs() -> None:
    seed = load_users(__import__("pathlib").Path(__file__).resolve().parents[2] / "zitadel-seed" / "users.yaml")
    rng = random.Random(42)

    plan = build_seed_plan(12, seed=seed, rng=rng)
    creators = {row[0] for row in plan}
    lobs = {row[1] for row in plan}

    assert len(plan) == 12
    assert creators <= {"mo-100", "mo-101", "mo-050", "mo-010"}
    assert lobs <= {"FICC", "FX", "DESK_RATES"}

    second = build_seed_plan(12, seed=seed, rng=random.Random(99))
    assert plan != second
