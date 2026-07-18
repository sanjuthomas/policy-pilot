from fastapi import Depends, Header, HTTPException

from authz.auth import subject_from_bearer_token, subject_from_obo_call
from authz.config import settings
from authz.models import Subject


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    return authorization.split(" ", 1)[1].strip()


def _strip_user_token(raw: str) -> str:
    token = raw.strip()
    if token.lower().startswith("bearer "):
        return token.split(" ", 1)[1].strip()
    return token


def require_obo_subject(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_on_behalf_of: str | None = Header(default=None, alias="X-On-Behalf-Of"),
    x_on_behalf_of_session_id: str | None = Header(
        default=None, alias="X-On-Behalf-Of-Session-Id"
    ),
) -> Subject:
    """Every authorization-service request must be service + OBO (fail closed).

    Missing ``X-On-Behalf-Of`` is rejected here — callers must not reach OPA.
    """
    if not settings.oidc_issuer_url:
        raise HTTPException(status_code=500, detail="OIDC issuer is not configured")

    if not x_on_behalf_of or not str(x_on_behalf_of).strip():
        raise HTTPException(
            status_code=403,
            detail=(
                "X-On-Behalf-Of user token is required; "
                "authorization-service does not accept service-only calls"
            ),
        )

    service_token = _parse_bearer(authorization)
    try:
        service_subject = subject_from_bearer_token(
            service_token, session_id=x_session_id
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=401,
            detail=f"OBO service token invalid: {exc.detail}",
        ) from exc

    if service_subject.user_id not in settings.authorized_service_user_id_set:
        raise HTTPException(
            status_code=403,
            detail=(
                f"service account {service_subject.user_id} is not authorized "
                "for authorization-service"
            ),
        )

    user_token = _strip_user_token(x_on_behalf_of)
    try:
        return subject_from_obo_call(
            service_token,
            user_token,
            service_session_id=x_session_id,
            user_session_id=x_on_behalf_of_session_id,
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=401,
            detail=f"OBO user token invalid: {exc.detail}",
        ) from exc


def get_compliance_subject(
    subject: Subject = Depends(require_obo_subject),
) -> Subject:
    """Compliance inquiry routes: OBO required, then compliance role check."""
    if not settings.compliance_role_set.intersection(subject.roles):
        raise HTTPException(
            status_code=403,
            detail="COMPLIANCE_ANALYST role required for policy inquiry",
        )
    return subject


# Back-compat alias used by evaluate routes (service + OBO already enforced above).
get_subject = require_obo_subject
