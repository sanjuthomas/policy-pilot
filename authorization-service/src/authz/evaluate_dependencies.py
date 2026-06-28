from __future__ import annotations

from fastapi import Header, HTTPException

from authz.auth import subject_from_bearer_token, subject_from_obo_call
from authz.config import settings
from authz.models import Subject


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    return authorization.split(" ", 1)[1].strip()


def _ensure_authorized_service(service_subject: Subject) -> None:
    if service_subject.user_id not in settings.authorized_service_user_id_set:
        raise HTTPException(
            status_code=403,
            detail=f"service account {service_subject.user_id} is not authorized for policy evaluation",
        )


def get_service_caller(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> Subject:
    if not settings.oidc_issuer_url:
        raise HTTPException(status_code=500, detail="OIDC issuer is not configured")

    service_token = _parse_bearer(authorization)
    try:
        service_subject = subject_from_bearer_token(service_token, session_id=x_session_id)
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail=str(exc.detail)) from exc

    _ensure_authorized_service(service_subject)
    return service_subject


def resolve_evaluate_subject(
    *,
    service_token: str,
    service_session_id: str | None,
    x_on_behalf_of: str | None,
    x_on_behalf_of_session_id: str | None,
    inline_subject: Subject | None,
) -> Subject:
    if x_on_behalf_of:
        user_token = x_on_behalf_of.strip()
        if user_token.lower().startswith("bearer "):
            user_token = user_token.split(" ", 1)[1].strip()
        return subject_from_obo_call(
            service_token,
            user_token,
            service_session_id=service_session_id,
            user_session_id=x_on_behalf_of_session_id,
        )

    if inline_subject is None:
        raise HTTPException(
            status_code=400,
            detail="subject is required when X-On-Behalf-Of is not provided",
        )
    return inline_subject
