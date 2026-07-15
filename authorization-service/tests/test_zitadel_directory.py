from __future__ import annotations

from authz.models import SeedUser
from authz.user_directory import UserDirectory
from authz.zitadel_directory import _to_seed_user
from zitadel_directory.models import DirectoryUser


def test_to_seed_user_maps_directory_user() -> None:
    seed = _to_seed_user(
        DirectoryUser(
            user_id="mo-100",
            given_name="Sarah",
            family_name="Chen",
            title="Analyst",
            roles=["INSTRUCTION_CREATOR"],
            groups=["MIDDLE_OFFICE"],
            covering_lobs=["FICC"],
            lob=None,
            supervisor_id="mo-050",
            zitadel_user_id="zid-1",
        )
    )
    assert seed.user_id == "mo-100"
    assert seed.roles == ["INSTRUCTION_CREATOR"]
    assert seed.supervisor_id == "mo-050"
    assert not hasattr(seed, "zitadel_user_id") or "zid-1" not in seed.model_dump()


def test_user_directory_provider_cache() -> None:
    calls = {"n": 0}

    def provider() -> list[SeedUser]:
        calls["n"] += 1
        return [
            SeedUser(
                user_id="pay-201",
                given_name="Sophie",
                family_name="Laurent",
                title="VP",
                roles=["FUNDING_APPROVER"],
                groups=["MIDDLE_OFFICE"],
                covering_lobs=["FICC"],
            )
        ]

    directory = UserDirectory.from_zitadel(
        email_domain="ssi.local",
        cache_ttl_seconds=60.0,
        provider=provider,
    )
    assert len(directory.all_users()) == 1
    assert len(directory.all_users()) == 1
    assert calls["n"] == 1
    assert directory.users_with_role("FUNDING_APPROVER")[0].user_id == "pay-201"
    assert directory.users_covering_lob("FICC")[0].user_id == "pay-201"


def test_from_zitadel_default_provider_disables_local_cache() -> None:
    directory = UserDirectory.from_zitadel(email_domain="ssi.local")
    assert directory._cache_ttl_seconds == 0.0
    assert directory._provider is not None
