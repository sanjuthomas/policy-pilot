from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from chat_application.config import settings


class AuthzOboClientError(Exception):
    pass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    allow_basis: list[str]
    violations: list[str]
    is_alert: bool


class AuthzOboClient:
    """Call authorization-service evaluate with service identity + user OBO.

    Authorization header must be an authorized service account (``svc-chat``).
    The logged-in user's session travels in ``X-On-Behalf-Of`` / session id, or
    the caller may pass an inline ``subject`` when OBO tokens are unavailable
    (tests / service-token-only evaluate).
    """

    def __init__(self, base_url: str | None = None, *, timeout: float = 15.0) -> None:
        self._base = (base_url or settings.authorization_service_url).rstrip("/")
        self._timeout = timeout

    async def evaluate_payment(
        self,
        *,
        action: str,
        payment: dict[str, Any],
        instruction_status: str = "",
        instruction_end_date: str = "",
        service_token: str | None = None,
        service_session_id: str | None = None,
        user_token: str | None = None,
        user_session_id: str | None = None,
        subject: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        if not service_token:
            raise AuthzOboClientError(
                "service token required for payment policy evaluation "
                "(chat service identity not logged in)"
            )

        payload: dict[str, Any] = {
            "action": action,
            "payment": payment,
            "instruction_status": instruction_status,
            "instruction_end_date": instruction_end_date,
        }
        headers = {
            "Authorization": f"Bearer {service_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if service_session_id:
            headers["X-Session-Id"] = service_session_id

        if user_token:
            headers["X-On-Behalf-Of"] = user_token
            if user_session_id:
                headers["X-On-Behalf-Of-Session-Id"] = user_session_id
        elif subject is not None:
            payload["subject"] = subject
        else:
            raise AuthzOboClientError(
                "user token (X-On-Behalf-Of) or inline subject is required"
            )

        url = f"{self._base}/api/v1/authorization/payments/evaluate"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AuthzOboClientError(
                f"authorization-service unreachable at {self._base}"
            ) from exc

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = str(response.json().get("detail", detail))
            except Exception:
                pass
            raise AuthzOboClientError(
                f"authorization-service rejected evaluate ({response.status_code}): {detail}"
            )

        body = response.json()
        return PolicyDecision(
            allowed=bool(body.get("allowed")),
            allow_basis=list(body.get("allow_basis") or []),
            violations=list(body.get("violations") or []),
            is_alert=bool(body.get("is_alert")),
        )
