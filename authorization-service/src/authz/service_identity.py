from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from authz.config import settings

logger = logging.getLogger(__name__)


def _zitadel_base() -> str:
    base = settings.zitadel_internal_url or settings.oidc_internal_url or settings.oidc_issuer_url
    if not base:
        raise RuntimeError("No Zitadel URL configured")
    return base.rstrip("/")


def _host_header() -> dict[str, str]:
    if not settings.oidc_issuer_url:
        return {}
    host = urlparse(settings.oidc_issuer_url).hostname or ""
    return {"Host": host} if host else {}


class ServiceIdentity:
    """Caches a Zitadel session for service-to-service ILM reads."""

    def __init__(self) -> None:
        self._session_token: str | None = None
        self._session_id: str | None = None

    @property
    def token(self) -> str | None:
        return self._session_token

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def login(self) -> None:
        if not settings.zitadel_service_pat:
            logger.warning("zitadel_service_pat not configured — ILM reads may fail")
            return

        user_id = settings.service_user_id
        password = settings.service_user_password

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
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
                "authorization-service authenticated as %s (session_id=%s)",
                user_id,
                self._session_id,
            )
        except Exception as exc:
            logger.error(
                "authorization-service could not authenticate as %s: %s",
                user_id,
                exc,
            )
            self._session_token = None
            self._session_id = None


service_identity = ServiceIdentity()
