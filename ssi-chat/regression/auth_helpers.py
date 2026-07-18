from __future__ import annotations

import os

import httpx

DEFAULT_ADMIN_USER = os.environ.get("HARNESS_ADMIN_USER", "admin-001")
DEFAULT_ADMIN_PASSWORD = os.environ.get("HARNESS_ADMIN_PASSWORD", "Password1!")
DEFAULT_COMPLIANCE_USER = os.environ.get("CHAT_COMPLIANCE_USER", "comp-001")
DEFAULT_COMPLIANCE_PASSWORD = os.environ.get("CHAT_COMPLIANCE_PASSWORD", "Password1!")
DEFAULT_SERVICE_USER = os.environ.get("SERVICE_USER_ID", "svc-chat")
DEFAULT_SERVICE_PASSWORD = os.environ.get("SERVICE_USER_PASSWORD", "Password1!")


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


def service_auth_headers(client: httpx.Client, base_url: str) -> dict[str, str]:
    """Login as svc-chat (or SERVICE_USER_ID) for domain-service Authorization."""
    return login_headers(
        client,
        base_url,
        user_id=DEFAULT_SERVICE_USER,
        password=DEFAULT_SERVICE_PASSWORD,
    )


def obo_headers(
    service_headers: dict[str, str],
    user_headers: dict[str, str],
) -> dict[str, str]:
    """Compose service Authorization + user JWT as X-On-Behalf-Of.

    Domain ``/api/v1`` APIs reject bare human JWTs; callers must use this shape.
    """
    service_auth = service_headers.get("Authorization", "")
    if not service_auth.startswith("Bearer "):
        raise ValueError("service_headers missing Bearer Authorization")
    user_auth = user_headers.get("Authorization", "")
    if not user_auth.startswith("Bearer "):
        raise ValueError("user_headers missing Bearer Authorization")
    user_token = user_auth.split(" ", 1)[1].strip()
    headers = {
        "Authorization": service_auth,
        "Accept": "application/json",
        "X-On-Behalf-Of": user_token,
    }
    if service_headers.get("X-Session-Id"):
        headers["X-Session-Id"] = service_headers["X-Session-Id"]
    if user_headers.get("X-Session-Id"):
        headers["X-On-Behalf-Of-Session-Id"] = user_headers["X-Session-Id"]
    return headers
