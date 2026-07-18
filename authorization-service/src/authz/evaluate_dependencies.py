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


def _identity_mismatch_fields(token_subject: Subject, inline: Subject) -> list[str]:
    """Compare security-relevant identity fields (not delegation metadata)."""
    mismatched: list[str] = []
    if token_subject.user_id != inline.user_id:
        mismatched.append("user_id")
    if token_subject.title != inline.title:
        mismatched.append("title")
    if token_subject.lob != inline.lob:
        mismatched.append("lob")
    if token_subject.supervisor_id != inline.supervisor_id:
        mismatched.append("supervisor_id")
    if sorted(token_subject.roles) != sorted(inline.roles):
        mismatched.append("roles")
    if sorted(token_subject.groups) != sorted(inline.groups):
        mismatched.append("groups")
    if sorted(token_subject.covering_lobs) != sorted(inline.covering_lobs):
        mismatched.append("covering_lobs")
    return mismatched


def resolve_evaluate_subject(
    *,
    service_token: str,
    service_session_id: str | None,
    x_on_behalf_of: str | None,
    x_on_behalf_of_session_id: str | None,
    inline_subject: Subject | None,
) -> Subject:
    """Resolve the human subject for lifecycle evaluate.

    OBO (verified user token) is always required. An optional inline ``subject``
    may be sent for the caller's bookkeeping; when present, identity fields must
    match the OBO-derived subject. OPA evaluation always uses the token-derived
    subject (including ``delegated_by`` from the Authorization service account).

    Eligible-approvers batch discovery is a separate endpoint and does not use
    this helper.
    """
    if not x_on_behalf_of or not str(x_on_behalf_of).strip():
        raise HTTPException(
            status_code=403,
            detail=(
                "X-On-Behalf-Of user token is required for lifecycle evaluate; "
                "inline subject alone is not accepted"
            ),
        )

    user_token = x_on_behalf_of.strip()
    if user_token.lower().startswith("bearer "):
        user_token = user_token.split(" ", 1)[1].strip()

    token_subject = subject_from_obo_call(
        service_token,
        user_token,
        service_session_id=service_session_id,
        user_session_id=x_on_behalf_of_session_id,
    )

    if inline_subject is not None:
        mismatched = _identity_mismatch_fields(token_subject, inline_subject)
        if mismatched:
            raise HTTPException(
                status_code=403,
                detail=(
                    "inline subject does not match X-On-Behalf-Of token identity: "
                    + ", ".join(mismatched)
                ),
            )

    return token_subject
