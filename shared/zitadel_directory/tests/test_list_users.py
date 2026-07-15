from __future__ import annotations

import base64
import json

import httpx
from zitadel_directory.client import ZitadelDirectoryClient


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def test_list_directory_users_hydrates_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v2/users":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {
                            "userId": "zid-1",
                            "username": "mo-100",
                            "human": {
                                "profile": {
                                    "givenName": "Sarah",
                                    "familyName": "Chen",
                                }
                            },
                        },
                        {
                            "userId": "zid-svc",
                            "username": "svc-instruction",
                            "machine": {"name": "svc"},
                        },
                    ]
                },
            )
        if path == "/v2/users/zid-1/metadata/search":
            meta = {
                "subject_user_id": "mo-100",
                "given_name": "Sarah",
                "family_name": "Chen",
                "title": "Analyst",
                "roles": json.dumps(["INSTRUCTION_CREATOR"]),
                "groups": json.dumps(["MIDDLE_OFFICE"]),
                "covering_lobs": json.dumps(["FICC"]),
            }
            return httpx.Response(
                200,
                json={
                    "metadata": [
                        {"key": key, "value": _b64(value)} for key, value in meta.items()
                    ]
                },
            )
        return httpx.Response(404, text=f"unexpected {path}")

    transport = httpx.MockTransport(handler)

    class _Client(ZitadelDirectoryClient):
        def _request(self, method, path, *, json_body=None):
            with httpx.Client(transport=transport, base_url=self._base_url) as client:
                response = client.request(
                    method,
                    path,
                    headers=self._headers,
                    json=json_body,
                )
            response.raise_for_status()
            return response.json()

    client = _Client(base_url="http://zitadel.test", pat="token")
    users = client.list_directory_users()
    assert len(users) == 1
    assert users[0].user_id == "mo-100"
    assert users[0].roles == ["INSTRUCTION_CREATOR"]
    assert users[0].covering_lobs == ["FICC"]


def test_client_requires_pat() -> None:
    try:
        ZitadelDirectoryClient(base_url="http://localhost:8080", pat="")
    except Exception as exc:
        assert "PAT" in str(exc)
    else:
        raise AssertionError("expected error")


def test_client_requires_base_url() -> None:
    try:
        ZitadelDirectoryClient(base_url="  ", pat="token")
    except Exception as exc:
        assert "base_url" in str(exc)
    else:
        raise AssertionError("expected error")


def test_list_skips_incomplete_and_metadata_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v2/users":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {"userId": "", "username": "orphan"},
                        {
                            "userId": "zid-skip",
                            "username": "svc-bot",
                            "human": {"profile": {}},
                        },
                        {
                            "userId": "zid-meta-fail",
                            "username": "broken",
                            "human": {"profile": {}},
                        },
                        {
                            "userId": "zid-incomplete",
                            "username": "no-title",
                            "human": {"profile": {"givenName": "No", "familyName": "Title"}},
                        },
                        {
                            "user_id": "zid-ok",
                            "username": "ok-user",
                            "preferredLoginName": "fallback@ssi.local",
                            "human": {"profile": {}},
                        },
                    ]
                },
            )
        if path == "/v2/users/zid-meta-fail/metadata/search":
            return httpx.Response(500, text="boom")
        if path == "/v2/users/zid-incomplete/metadata/search":
            return httpx.Response(
                200,
                json={
                    "metadata": [
                        {"key": "roles", "value": _b64(json.dumps(["INSTRUCTION_CREATOR"]))}
                    ]
                },
            )
        if path == "/v2/users/zid-ok/metadata/search":
            meta = {
                "title": "Analyst",
                "roles": "INSTRUCTION_CREATOR,PAYMENT_CREATOR",
                "groups": json.dumps("not-a-list"),
                "covering_lobs": json.dumps(["FX"]),
            }
            return httpx.Response(
                200,
                json={
                    "metadata": [
                        {"key": key, "value": _b64(value)} for key, value in meta.items()
                    ]
                    + [{"key": 1, "value": "x"}, {"not": "dict"}]
                },
            )
        return httpx.Response(404, text=f"unexpected {path}")

    transport = httpx.MockTransport(handler)

    class _Client(ZitadelDirectoryClient):
        def _request(self, method, path, *, json_body=None):
            with httpx.Client(transport=transport, base_url=self._base_url) as client:
                response = client.request(
                    method,
                    path,
                    headers=self._headers,
                    json=json_body,
                )
            if response.status_code >= 400:
                from zitadel_directory.client import ZitadelDirectoryError

                raise ZitadelDirectoryError(f"{method} {path} failed")
            return response.json()

    client = _Client(base_url="http://zitadel.test", pat="token")
    users = client.list_directory_users()
    assert len(users) == 1
    assert users[0].user_id == "ok-user"
    assert users[0].roles == ["INSTRUCTION_CREATOR", "PAYMENT_CREATOR"]
    assert users[0].groups == []


def test_request_error_and_empty_paths() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="unavailable")
        if calls["n"] == 2:
            return httpx.Response(200, content=b"")
        return httpx.Response(200, json=["not", "an", "object"])

    transport = httpx.MockTransport(handler)
    client = ZitadelDirectoryClient(base_url="http://zitadel.test", pat="token")

    import zitadel_directory.client as client_mod

    original = client_mod.httpx.Client

    class _MockClient(original):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    client_mod.httpx.Client = _MockClient  # type: ignore[misc]
    try:
        from zitadel_directory.client import ZitadelDirectoryError

        try:
            client._request("GET", "/fail")
        except ZitadelDirectoryError as exc:
            assert "503" in str(exc)
        else:
            raise AssertionError("expected 503 error")

        assert client._request("GET", "/empty") == {}

        try:
            client._request("GET", "/list")
        except ZitadelDirectoryError as exc:
            assert "non-object" in str(exc)
        else:
            raise AssertionError("expected non-object error")
    finally:
        client_mod.httpx.Client = original  # type: ignore[misc]


def test_resolve_org_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/management/v1/orgs/me":
            return httpx.Response(200, json={"org": {"id": "org-1"}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    class _Client(ZitadelDirectoryClient):
        def _request(self, method, path, *, json_body=None):
            with httpx.Client(transport=transport, base_url=self._base_url) as client:
                response = client.request(
                    method,
                    path,
                    headers=self._headers,
                    json=json_body,
                )
            response.raise_for_status()
            return response.json()

    client = _Client(base_url="http://zitadel.test", pat="token")
    assert client.resolve_org_id() == "org-1"
    scoped = client.with_org("org-2")
    assert scoped._headers.get("x-zitadel-orgid") == "org-2"
