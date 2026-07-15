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
