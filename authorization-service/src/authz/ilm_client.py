"""HTTP client for calling the Instruction Lifecycle Manager."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from authz.config import settings

logger = logging.getLogger(__name__)


class IlmError(Exception):
    pass


class InstructionNotFoundError(IlmError):
    pass


class IlmClient:
    def __init__(self) -> None:
        self._base = settings.ilm_url.rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        from authz.service_identity import service_identity

        headers: dict[str, str] = {}
        if service_identity.token:
            headers["Authorization"] = f"Bearer {service_identity.token}"
            if service_identity.session_id:
                headers["X-Session-Id"] = service_identity.session_id
        return headers

    async def get_instruction(self, instruction_id: str) -> dict[str, Any]:
        url = f"{self._base}/api/v1/instructions/{instruction_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._auth_headers())

        if resp.status_code == 404:
            raise InstructionNotFoundError(f"instruction {instruction_id} not found")
        resp.raise_for_status()
        return resp.json()
