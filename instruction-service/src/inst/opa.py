from __future__ import annotations

from typing import Any

import httpx

from inst.authorization import (
    PolicyDecision,
    build_authorization_block,
    instruction_resource_context,
)
from inst.config import settings
from inst.models.api import Subject
from inst.models.enums import LifecycleAction
from inst.models.instruction import CashSettlementInstruction


class PolicyDeniedError(Exception):
    pass


class OpaClient:
    _PACKAGE = "instruction/lifecycle"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.opa_url).rstrip("/")

    async def _post_data(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.base_url}/v1/data/{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        return body.get("result")

    def _build_payload(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
    ) -> dict[str, Any]:
        return {
            "input": {
                "action": action.value,
                "subject": subject.to_opa_subject(),
                "instruction": instruction.to_opa_instruction(),
                "account": instruction.to_opa_account(),
            }
        }

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    @staticmethod
    def _violation_codes(value: Any) -> list[str]:
        if not isinstance(value, dict):
            return []
        return sorted(key for key, enabled in value.items() if enabled)

    async def evaluate(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
    ) -> PolicyDecision:
        payload = self._build_payload(action, subject, instruction)
        allowed = bool(await self._post_data(f"{self._PACKAGE}/allow", payload))
        if allowed:
            basis = self._as_string_list(
                await self._post_data(f"{self._PACKAGE}/allow_basis", payload)
            )
            return PolicyDecision(
                allowed=True,
                allow_basis=basis,
                violations=[],
                is_alert=False,
            )

        violations = self._violation_codes(
            await self._post_data(f"{self._PACKAGE}/violations", payload)
        )
        is_alert = bool(await self._post_data(f"{self._PACKAGE}/is_alert", payload))
        return PolicyDecision(
            allowed=False,
            allow_basis=[],
            violations=violations,
            is_alert=is_alert,
        )

    async def is_allowed(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
    ) -> bool:
        return (await self.evaluate(action, subject, instruction)).allowed

    async def authorize(
        self,
        action: LifecycleAction,
        subject: Subject,
        instruction: CashSettlementInstruction,
    ) -> dict[str, Any]:
        decision = await self.evaluate(action, subject, instruction)
        authorization = build_authorization_block(
            decision,
            subject,
            action,
            resource_context=instruction_resource_context(instruction),
        )
        if not decision.allowed:
            raise PolicyDeniedError(authorization["summary"])
        return authorization
