from __future__ import annotations

from typing import Any

import httpx

from ps.authorization import (
    PolicyDecision,
    build_authorization_block,
    payment_resource_context,
)
from ps.config import settings
from ps.models.api import Subject
from ps.models.enums import PaymentAction
from ps.models.payment import Payment


class PolicyDeniedError(Exception):
    pass


class OpaClient:
    _PACKAGE = "payment/lifecycle"

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
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> dict[str, Any]:
        return {
            "input": {
                "action": action.value,
                "subject": subject.to_opa_subject(),
                "payment": payment.to_opa_payment(
                    instruction_end_date=instruction_end_date,
                    instruction_status=instruction_status,
                ),
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
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str = "",
        instruction_status: str = "",
    ) -> PolicyDecision:
        payload = self._build_payload(
            action,
            subject,
            payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
        )
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
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> bool:
        return (
            await self.evaluate(
                action,
                subject,
                payment,
                instruction_end_date=instruction_end_date,
                instruction_status=instruction_status,
            )
        ).allowed

    async def authorize(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str = "",
        instruction_status: str = "",
    ) -> dict[str, Any]:
        decision = await self.evaluate(
            action,
            subject,
            payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
        )
        authorization = build_authorization_block(
            decision,
            subject,
            action,
            resource_context=payment_resource_context(
                payment,
                instruction_status=instruction_status,
                instruction_end_date=instruction_end_date,
            ),
        )
        if not decision.allowed:
            raise PolicyDeniedError(authorization["summary"])
        return authorization
