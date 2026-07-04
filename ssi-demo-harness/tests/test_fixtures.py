from __future__ import annotations

import pytest
from harness.fixtures import (
    SeedFile,
    SeedUser,
    build_instruction_payload,
    load_users,
    user_by_id,
)


def test_build_instruction_payload_defaults() -> None:
    payload = build_instruction_payload()
    assert payload["instruction_type"] == "SINGLE_USE"
    assert payload["owning_lob"] == "FICC"
    assert payload["currency"] == "USD"
    assert payload["funding_account"]["owning_lob"] == "FICC"


def test_user_by_id() -> None:
    seed = SeedFile(
        users=[
            SeedUser(
                user_id="mo-100",
                given_name="Alex",
                family_name="Chen",
                title="VP",
                roles=["MIDDLE_OFFICE"],
            )
        ]
    )
    user = user_by_id(seed, "mo-100")
    assert user.family_name == "Chen"


def test_user_by_id_missing_raises() -> None:
    seed = SeedFile(users=[])
    with pytest.raises(KeyError, match="unknown user_id"):
        user_by_id(seed, "missing")


def test_load_users_from_repo_seed() -> None:
    users_file = (
        __import__("pathlib").Path(__file__).resolve().parents[2] / "zitadel-seed" / "users.yaml"
    )
    if not users_file.is_file():
        pytest.skip("zitadel-seed/users.yaml not available")
    seed = load_users(users_file)
    assert seed.users
    assert seed.defaults.get("password")
