from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import Header, HTTPException
from platform_auth import LoginRequest, ZitadelLoginClient
from pydantic import BaseModel

from audit_console.config import settings


class AuditorSubject(BaseModel):
    user_id: str
    title: str
    roles: list[str]
    groups: list[str]


def zitadel_base() -> str:
    base = (
        settings.zitadel_internal_url
        or settings.oidc_internal_url
        or settings.oidc_issuer_url
    )
    return base.rstrip("/")


def zitadel_headers() -> dict[str, str]:
    host = urlparse(settings.oidc_issuer_url).netloc
    return {"Host": host} if host else {}


def decode_metadata(raw: dict[str, Any]) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str):
            continue
        try:
            decoded[key] = base64.b64decode(value).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded[key] = value
    return decoded


def parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = [part.strip() for part in raw.split(",") if part.strip()]
    return [str(item) for item in value] if isinstance(value, list) else []


async def resolve_auditor(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> AuditorSubject:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    if not session_id:
        raise HTTPException(status_code=401, detail="X-Session-Id required")
    if not settings.zitadel_service_pat:
        raise HTTPException(status_code=503, detail="ZITADEL service PAT not configured")

    session_token = authorization.split(" ", 1)[1].strip()
    headers = {
        **zitadel_headers(),
        "Authorization": f"Bearer {settings.zitadel_service_pat}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            session_response = await client.get(
                f"{zitadel_base()}/v2/sessions/{session_id}",
                headers=headers,
                params={"sessionToken": session_token},
            )
            session_response.raise_for_status()
            session = session_response.json().get("session") or {}
            user = ((session.get("factors") or {}).get("user") or {})
            zitadel_user_id = user.get("id")
            if not zitadel_user_id:
                raise ValueError("session response missing user id")

            metadata_response = await client.post(
                f"{zitadel_base()}/v2/users/{zitadel_user_id}/metadata/search",
                headers={**headers, "Content-Type": "application/json"},
                json={},
            )
            metadata_response.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=401, detail=f"could not resolve auditor session: {exc}"
        ) from exc

    raw = {
        item["key"]: item["value"]
        for item in metadata_response.json().get("metadata") or []
        if isinstance(item.get("key"), str) and isinstance(item.get("value"), str)
    }
    metadata = decode_metadata(raw)
    subject = AuditorSubject(
        user_id=metadata.get("subject_user_id") or str(user.get("loginName") or ""),
        title=metadata.get("title") or "Technology Auditor",
        roles=parse_list(metadata.get("roles")),
        groups=parse_list(metadata.get("groups")),
    )
    if settings.required_group not in subject.groups:
        raise HTTPException(
            status_code=403,
            detail=f"membership in {settings.required_group} is required",
        )
    return subject


def login_client() -> ZitadelLoginClient:
    if not settings.zitadel_service_pat:
        raise HTTPException(status_code=503, detail="ZITADEL service PAT not configured")
    return ZitadelLoginClient(
        zitadel_base(),
        settings.zitadel_service_pat,
        host_header=urlparse(settings.oidc_issuer_url).hostname or "",
    )


async def login(request: LoginRequest) -> dict[str, str]:
    try:
        session = login_client().login(request.user_id, request.password)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"login failed: {exc}") from exc
    return {
        "user_id": session.user_id,
        "session_id": session.session_id,
        "session_token": session.session_token,
    }
