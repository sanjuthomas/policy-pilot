from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

try:
    from telemetry import get_meter, record_counter

    _login_meter = get_meter("platform_auth.login")
except ImportError:  # pragma: no cover
    _login_meter = None


def _record_login_metric(*, result: str, user_id: str) -> None:
    if _login_meter is None:
        return
    record_counter(
        _login_meter,
        "platform_auth.login.total",
        attributes={"result": result, "user_id": user_id},
    )


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


@dataclass(frozen=True)
class SessionCredentials:
    user_id: str
    session_id: str
    session_token: str


class ZitadelLoginClient:
    def __init__(
        self,
        base_url: str,
        service_pat: str,
        *,
        host_header: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_pat = service_pat
        self.host_header = host_header.strip()

    def login(self, user_id: str, password: str) -> SessionCredentials:
        candidates = [user_id]
        if "@" in user_id:
            candidates.append(user_id.split("@", 1)[0])

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                session = self._create_session(candidate, password)
                _record_login_metric(result="success", user_id=session.user_id)
                return session
            except httpx.HTTPStatusError as exc:
                last_error = exc
        _record_login_metric(result="failure", user_id=user_id.split("@", 1)[0])
        if last_error is not None:
            raise last_error
        raise RuntimeError("login failed")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.service_pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.host_header:
            headers["Host"] = self.host_header
        return headers

    def _create_session(self, login_name: str, password: str) -> SessionCredentials:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/v2/sessions",
                headers=self._headers(),
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
        return SessionCredentials(
            user_id=login_name.split("@", 1)[0],
            session_id=session_id,
            session_token=session_token,
        )
