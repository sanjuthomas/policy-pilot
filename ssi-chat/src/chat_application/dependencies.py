from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from chat_application.auth import subject_from_bearer_token
from chat_application.config import settings
from chat_application.subject import Subject


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


def get_compliance_subject(subject: Subject = Depends(get_subject)) -> Subject:
    if not settings.compliance_role_set.intersection(subject.roles):
        raise HTTPException(
            status_code=403,
            detail="COMPLIANCE_ANALYST role required for chat",
        )
    return subject
