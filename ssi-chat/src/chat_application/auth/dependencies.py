from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from chat_application.auth.bearer import subject_from_bearer_token
from chat_application.auth.subject import Subject
from chat_application.config import settings


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


def get_chat_subject(subject: Subject = Depends(get_subject)) -> Subject:
    """Allow compliance, FO/MO instruction analysts, and payment actors."""
    if not settings.chat_role_set.intersection(subject.roles):
        raise HTTPException(
            status_code=403,
            detail=(
                "Chat requires COMPLIANCE_ANALYST, PAYMENT_CREATOR, FUNDING_APPROVER, "
                "INSTRUCTION_CREATOR, or INSTRUCTION_APPROVER"
            ),
        )
    return subject
