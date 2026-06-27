from __future__ import annotations

from dataclasses import dataclass

import httpx

from chat_application.config import settings


@dataclass(frozen=True)
class SessionCredentials:
    session_id: str
    session_token: str
    user_id: str


class ZitadelAuthClient:
    """Authenticate compliance users via the ZITADEL Session API."""

    def __init__(
        self,
        base_url: str | None = None,
        service_pat: str | None = None,
        *,
        host_header: str = "",
    ) -> None:
        self.base_url = (base_url or settings.zitadel_url).rstrip("/")
        self.service_pat = service_pat or settings.zitadel_service_pat or ""
        self.host_header = (host_header or settings.zitadel_host_header).strip()

    def _request_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.service_pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.host_header:
            headers["Host"] = self.host_header
        return headers

    async def login(self, login_name: str, password: str) -> SessionCredentials:
        candidates = [login_name]
        if "@" in login_name:
            candidates.append(login_name.split("@", 1)[0])

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                return await self._create_session(candidate, password)
            except httpx.HTTPStatusError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("login failed")

    async def _create_session(self, login_name: str, password: str) -> SessionCredentials:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v2/sessions",
                headers=self._request_headers(),
                json={
                    "checks": {
                        "user": {"loginName": login_name},
                        "password": {"password": password},
                    }
                },
            )
            response.raise_for_status()
            body = response.json()

        session_id = body.get("sessionId") or body.get("session_id")
        session_token = body.get("sessionToken") or body.get("session_token")
        if not session_id or not session_token:
            raise RuntimeError(f"ZITADEL session response missing session fields: {body}")

        user_id = login_name.split("@", 1)[0]
        return SessionCredentials(
            session_id=session_id,
            session_token=session_token,
            user_id=user_id,
        )


def login_name_for_user(user_id: str, email_domain: str = "ssi.local") -> str:
    if "@" in user_id:
        return user_id
    return f"{user_id}@{email_domain}"
