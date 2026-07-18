from __future__ import annotations

from fastapi import Header, HTTPException
from platform_auth import require_platform_admin

from ps.auth import subject_from_bearer_token
from ps.config import settings
from ps.models.api import Subject


def get_admin_subject(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> Subject:
    """Platform-admin console auth (direct JWT — not OBO).

    ``/api/ui/*`` is the admin browser console; it authenticates as the admin
    user directly. Domain APIs under ``/api/v1`` always require OBO.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    if not settings.oidc_issuer_url:
        raise HTTPException(status_code=500, detail="OIDC issuer is not configured")
    token = authorization.split(" ", 1)[1].strip()
    subject = subject_from_bearer_token(token, session_id=x_session_id)
    return require_platform_admin(subject)  # type: ignore[return-value]
