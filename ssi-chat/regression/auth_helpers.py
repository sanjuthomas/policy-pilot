from __future__ import annotations

import os

import httpx

DEFAULT_ADMIN_USER = os.environ.get("HARNESS_ADMIN_USER", "admin-001")
DEFAULT_ADMIN_PASSWORD = os.environ.get("HARNESS_ADMIN_PASSWORD", "Password1!")
DEFAULT_COMPLIANCE_USER = os.environ.get("CHAT_COMPLIANCE_USER", "comp-001")
DEFAULT_COMPLIANCE_PASSWORD = os.environ.get("CHAT_COMPLIANCE_PASSWORD", "Password1!")


def login_headers(
    client: httpx.Client,
    base_url: str,
    *,
    user_id: str,
    password: str,
) -> dict[str, str]:
    response = client.post(
        f"{base_url.rstrip('/')}/api/auth/login",
        json={"user_id": user_id, "password": password},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "Authorization": f"Bearer {payload['session_token']}",
        "X-Session-Id": payload["session_id"],
    }


def admin_auth_headers(client: httpx.Client, base_url: str) -> dict[str, str]:
    return login_headers(
        client,
        base_url,
        user_id=DEFAULT_ADMIN_USER,
        password=DEFAULT_ADMIN_PASSWORD,
    )


def compliance_auth_headers(client: httpx.Client, base_url: str) -> dict[str, str]:
    return login_headers(
        client,
        base_url,
        user_id=DEFAULT_COMPLIANCE_USER,
        password=DEFAULT_COMPLIANCE_PASSWORD,
    )
