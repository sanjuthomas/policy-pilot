"""HTTP client for calling the instruction service."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ps.config import settings

logger = logging.getLogger(__name__)


class InstructionServiceClientError(Exception):
    pass


class InstructionNotFoundError(InstructionServiceClientError):
    pass


class InstructionStateError(InstructionServiceClientError):
    """Instruction is in the wrong state (e.g. already USED, expired)."""


class InstructionServiceClient:
    """Thin async HTTP client over the instruction-service REST API.

    Forwards the caller's Bearer token (+ optional X-Session-Id) so that
    service-to-service calls work regardless of auth mode.
    """

    def __init__(self) -> None:
        self._base = settings.instruction_service_url.rstrip("/")

    async def _auth_headers(
        self,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, str]:
        """Build auth headers using the OBO delegation pattern.

        If the service has its own session token (from ``service_identity``):
          - ``Authorization: Bearer <service-token>``  — service identity
          - ``X-On-Behalf-Of: <user-token>``           — original user
          - ``X-On-Behalf-Of-Session-Id: <session>``   — user's session ID

        If the service has no token yet (startup race / misconfiguration):
          - Fall back to forwarding the user's token directly in ``Authorization``
            so the call still works, just without delegation metadata.
        """
        from ps.service_identity import service_identity

        if bearer_token and not service_identity.token:
            await service_identity.ensure_logged_in()

        svc_token = service_identity.token

        if svc_token and bearer_token:
            headers: dict[str, str] = {"Authorization": f"Bearer {svc_token}"}
            if service_identity.session_id:
                headers["X-Session-Id"] = service_identity.session_id
            headers["X-On-Behalf-Of"] = bearer_token
            if session_id:
                headers["X-On-Behalf-Of-Session-Id"] = session_id
            return headers

        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if session_id:
            headers["X-Session-Id"] = session_id
        return headers

    async def get_instruction(
        self,
        instruction_id: str,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base}/api/v1/instructions/{instruction_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url, headers=await self._auth_headers(bearer_token, session_id)
            )

        if resp.status_code == 404:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        resp.raise_for_status()
        return resp.json()

    async def get_instruction_as_service(self, instruction_id: str) -> dict[str, Any]:
        """Read instruction context using the payment-service service account only."""
        from ps.service_identity import service_identity

        await service_identity.ensure_logged_in()
        headers: dict[str, str] = {}
        if service_identity.token:
            headers["Authorization"] = f"Bearer {service_identity.token}"
        if service_identity.session_id:
            headers["X-Session-Id"] = service_identity.session_id

        url = f"{self._base}/api/v1/instructions/{instruction_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        resp.raise_for_status()
        return resp.json()

    async def mark_used(
        self,
        instruction_id: str,
        payment_id: str,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Call instruction-service USE endpoint for SINGLE_USE instructions at submit."""
        url = f"{self._base}/api/v1/instructions/{instruction_id}/use"
        body = {
            "payment_reference": payment_id,
            "end_to_end_identification": payment_id[:35],
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json=body,
                headers=await self._auth_headers(bearer_token, session_id),
            )

        if resp.status_code == 404:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        if resp.status_code == 409:
            raise InstructionStateError(
                f"instruction {instruction_id} cannot be marked USED: {resp.text}"
            )
        resp.raise_for_status()
        return resp.json()

    async def release_use(
        self,
        instruction_id: str,
        payment_id: str,
        *,
        bearer_token: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Revert a SINGLE_USE instruction from USED to APPROVED after payment cancel/reject."""
        url = f"{self._base}/api/v1/instructions/{instruction_id}/release-use"
        body = {"payment_reference": payment_id}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json=body,
                headers=await self._auth_headers(bearer_token, session_id),
            )

        if resp.status_code == 404:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        if resp.status_code == 409:
            raise InstructionStateError(
                f"instruction {instruction_id} cannot be released: {resp.text}"
            )
        resp.raise_for_status()
        return resp.json()
