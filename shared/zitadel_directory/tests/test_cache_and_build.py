from __future__ import annotations

import pytest

from zitadel_directory.cache import DirectoryCache
from zitadel_directory.client import (
    ZitadelDirectoryClient,
    ZitadelDirectoryError,
    build_directory_client,
)
from zitadel_directory.models import DirectoryUser


def test_directory_user_seed_fields_excludes_zitadel_id() -> None:
    user = DirectoryUser(
        user_id="mo-100",
        given_name="Sarah",
        family_name="Chen",
        title="Analyst",
        roles=["INSTRUCTION_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FICC"],
        supervisor_id="mo-050",
        zitadel_user_id="zid-1",
    )
    fields = user.seed_fields()
    assert "zitadel_user_id" not in fields
    assert fields["user_id"] == "mo-100"
    assert fields["supervisor_id"] == "mo-050"


def test_directory_cache_ttl_and_force_refresh() -> None:
    calls = {"n": 0}

    class _Client(ZitadelDirectoryClient):
        def list_directory_users(self) -> list[DirectoryUser]:
            calls["n"] += 1
            return [
                DirectoryUser(
                    user_id=f"u-{calls['n']}",
                    given_name="A",
                    family_name="B",
                    title="Analyst",
                    roles=["INSTRUCTION_CREATOR"],
                )
            ]

    cache = DirectoryCache(lambda: _Client(base_url="http://z.test", pat="token"), ttl_seconds=60.0)
    assert cache.ttl_seconds == 60.0
    first = cache.list_users()
    second = cache.list_users()
    assert calls["n"] == 1
    assert first[0].user_id == second[0].user_id == "u-1"

    third = cache.list_users(force_refresh=True)
    assert calls["n"] == 2
    assert third[0].user_id == "u-2"

    cache.clear()
    fourth = cache.list_users()
    assert calls["n"] == 3
    assert fourth[0].user_id == "u-3"


def test_build_directory_client_without_org_attach() -> None:
    client = build_directory_client(
        base_url="http://zitadel.test",
        pat="token",
        attach_org=False,
    )
    assert "x-zitadel-orgid" not in client._headers


def test_build_directory_client_org_fallback(monkeypatch) -> None:
    def _boom(self, org_id: str | None = None):
        raise ZitadelDirectoryError("GET /management/v1/orgs/me failed (404): not found")

    monkeypatch.setattr(ZitadelDirectoryClient, "with_org", _boom)
    client = build_directory_client(
        base_url="http://zitadel.test",
        pat="token",
        attach_org=True,
    )
    assert isinstance(client, ZitadelDirectoryClient)
    assert "x-zitadel-orgid" not in client._headers


def test_build_directory_client_unexpected_org_error_propagates(monkeypatch) -> None:
    """Non-directory errors must not be swallowed (issue #54 / P2-3)."""

    def _boom(self, org_id: str | None = None):
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(ZitadelDirectoryClient, "with_org", _boom)
    with pytest.raises(RuntimeError, match="unexpected bug"):
        build_directory_client(
            base_url="http://zitadel.test",
            pat="token",
            attach_org=True,
        )
