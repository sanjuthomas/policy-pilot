from __future__ import annotations

from fastapi import Header, HTTPException

from harness.auth import subject_from_bearer_token
from harness.config import settings
from harness.models import Subject
from harness.zitadel_auth import SessionCredentials


def get_subject(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> Subject:
    has_bearer = authorization is not None and authorization.lower().startswith("bearer ")
    if not has_bearer:
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    if not settings.oidc_issuer_url:
        raise HTTPException(status_code=500, detail="OIDC issuer is not configured")
    token = authorization.split(" ", 1)[1].strip()
    return subject_from_bearer_token(token, session_id=x_session_id)


def get_admin_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> SessionCredentials:
    has_bearer = authorization is not None and authorization.lower().startswith("bearer ")
    if not has_bearer or not x_session_id:
        raise HTTPException(
            status_code=401,
            detail="Authorization Bearer token and X-Session-Id required",
        )
    token = authorization.split(" ", 1)[1].strip()
    return SessionCredentials(session_id=x_session_id, session_token=token)
