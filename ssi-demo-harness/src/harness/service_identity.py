"""Harness service identity for domain-service OBO calls."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from harness.config import settings

logger = logging.getLogger(__name__)


def _zitadel_base() -> str:
    base = settings.zitadel_internal_url or settings.zitadel_url or settings.oidc_issuer_url
    if not base:
        raise RuntimeError("No Zitadel URL configured")
    return base.rstrip("/")


def _host_header() -> dict[str, str]:
    if settings.zitadel_host_header:
        return {"Host": settings.zitadel_host_header}
    if not settings.oidc_issuer_url:
        return {}
    host = urlparse(settings.oidc_issuer_url).hostname or ""
    return {"Host": host} if host else {}


class ServiceIdentity:
    """Holds a service-account session (default ``svc-chat``) for OBO calls."""

    def __init__(self) -> None:
        self._session_token: str | None = None
        self._session_id: str | None = None

    @property
    def token(self) -> str | None:
        return self._session_token

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def login(self) -> None:
        if not settings.zitadel_service_pat:
            logger.warning(
                "zitadel_service_pat not configured — domain OBO calls unavailable"
            )
            return

        user_id = settings.service_user_id
        password = settings.service_user_password
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{_zitadel_base()}/v2/sessions",
                headers={
                    **_host_header(),
                    "Authorization": f"Bearer {settings.zitadel_service_pat}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "checks": {
                        "user": {"loginName": user_id},
                        "password": {"password": password},
                    }
                },
            )
            resp.raise_for_status()
            body = resp.json()

        self._session_id = body.get("sessionId") or body.get("session_id")
        self._session_token = body.get("sessionToken") or body.get("session_token")
        if not self._session_token:
            raise ValueError(f"Zitadel session response missing token: {body}")
        logger.info(
            "harness authenticated as %s (session_id=%s)",
            user_id,
            self._session_id,
        )

    def ensure_logged_in(self) -> None:
        if not self._session_token:
            self.login()


service_identity = ServiceIdentity()


def obo_headers(session) -> dict[str, str]:
    """svc-* Authorization + user session as X-On-Behalf-Of."""
    service_identity.ensure_logged_in()
    if not service_identity.token:
        raise RuntimeError("harness service identity not logged in")
    headers = {
        "Authorization": f"Bearer {service_identity.token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-On-Behalf-Of": session.session_token,
    }
    if service_identity.session_id:
        headers["X-Session-Id"] = service_identity.session_id
    if getattr(session, "session_id", None):
        headers["X-On-Behalf-Of-Session-Id"] = session.session_id
    return headers
