from __future__ import annotations

from typing import Any

import httpx

from authz.config import settings
from authz.models import PaymentRecord, Subject


class OpaClient:
    _PAYMENT_PACKAGE = "payment/lifecycle"
    _PAYMENT_ACTION = "APPROVE_PAYMENT"
    _INSTRUCTION_PACKAGE = "instruction/lifecycle"
    _INSTRUCTION_ACTION = "APPROVE"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.opa_url).rstrip("/")

    async def _post_data(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.base_url}/v1/data/{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        return body.get("result")

    def _build_payment_payload(
        self,
        subject: Subject,
        payment: PaymentRecord,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> dict[str, Any]:
        return {
            "input": {
                "action": self._PAYMENT_ACTION,
                "subject": subject.to_opa_subject(),
                "payment": payment.to_opa_payment(
                    instruction_end_date=instruction_end_date,
                    instruction_status=instruction_status,
                ),
            }
        }

    def _build_instruction_payload(
        self,
        subject: Subject,
        *,
        opa_instruction: dict[str, Any],
        opa_account: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "input": {
                "action": self._INSTRUCTION_ACTION,
                "subject": subject.to_opa_subject(),
                "instruction": opa_instruction,
                "account": opa_account,
            }
        }

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    async def can_approve_payment(
        self,
        subject: Subject,
        payment: PaymentRecord,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> tuple[bool, list[str]]:
        payload = self._build_payment_payload(
            subject,
            payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
        )
        allowed = bool(await self._post_data(f"{self._PAYMENT_PACKAGE}/allow", payload))
        if not allowed:
            return False, []
        basis = self._as_string_list(
            await self._post_data(f"{self._PAYMENT_PACKAGE}/allow_basis", payload)
        )
        return True, basis

    async def can_approve_instruction(
        self,
        subject: Subject,
        *,
        opa_instruction: dict[str, Any],
        opa_account: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        payload = self._build_instruction_payload(
            subject,
            opa_instruction=opa_instruction,
            opa_account=opa_account,
        )
        allowed = bool(await self._post_data(f"{self._INSTRUCTION_PACKAGE}/allow", payload))
        if not allowed:
            return False, []
        basis = self._as_string_list(
            await self._post_data(f"{self._INSTRUCTION_PACKAGE}/allow_basis", payload)
        )
        return True, basis
