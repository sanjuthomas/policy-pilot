from __future__ import annotations

from typing import Any

import httpx

from chat_application.auth.service_identity import service_identity
from chat_application.config import settings


class InstructionClientError(Exception):
    pass


class InstructionNotFoundError(InstructionClientError):
    pass


class InstructionClient:
    """Fetch instructions for skill preflight (user JWT or svc-chat OBO)."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 15.0) -> None:
        self._base = (base_url or settings.instruction_service_url).rstrip("/")
        self._timeout = timeout

    def _headers(
        self,
        *,
        user_token: str | None,
        user_session_id: str | None,
    ) -> dict[str, str]:
        svc_token = service_identity.token
        if svc_token and user_token:
            headers = {
                "Authorization": f"Bearer {svc_token}",
                "Accept": "application/json",
                "X-On-Behalf-Of": user_token,
            }
            if service_identity.session_id:
                headers["X-Session-Id"] = service_identity.session_id
            if user_session_id:
                headers["X-On-Behalf-Of-Session-Id"] = user_session_id
            return headers

        headers: dict[str, str] = {"Accept": "application/json"}
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"
        if user_session_id:
            headers["X-Session-Id"] = user_session_id
        return headers

    async def get_instruction(
        self,
        instruction_id: str,
        *,
        user_token: str | None,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        url = f"{self._base}/api/v1/instructions/{instruction_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers=self._headers(
                        user_token=user_token,
                        user_session_id=user_session_id,
                    ),
                )
        except httpx.HTTPError as exc:
            raise InstructionClientError(
                f"instruction-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 404:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = str(response.json().get("detail", detail))
            except Exception:
                pass
            raise InstructionClientError(
                f"instruction-service rejected GET ({response.status_code}): {detail}"
            )
        return response.json()
