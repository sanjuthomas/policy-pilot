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
    """Fetch instructions for skill preflight (svc-chat + user OBO)."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 15.0) -> None:
        self._base = (base_url or settings.instruction_service_url).rstrip("/")
        self._timeout = timeout

    async def _obo_headers(
        self,
        *,
        user_token: str,
        user_session_id: str | None,
    ) -> dict[str, str]:
        if not service_identity.token:
            await service_identity.ensure_logged_in()
        if not service_identity.token:
            raise InstructionClientError(
                "chat service identity not logged in — cannot call instruction-service with OBO"
            )
        headers = {
            "Authorization": f"Bearer {service_identity.token}",
            "Accept": "application/json",
            "X-On-Behalf-Of": user_token,
        }
        if service_identity.session_id:
            headers["X-Session-Id"] = service_identity.session_id
        if user_session_id:
            headers["X-On-Behalf-Of-Session-Id"] = user_session_id
        return headers

    async def get_instruction(
        self,
        instruction_id: str,
        *,
        user_token: str | None,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        if not user_token:
            raise InstructionClientError(
                "user token (X-On-Behalf-Of) is required for instruction-service"
            )
        url = f"{self._base}/api/v1/instructions/{instruction_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    headers=await self._obo_headers(
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
