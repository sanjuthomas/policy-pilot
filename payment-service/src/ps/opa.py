from typing import Any

import httpx

from ps.config import settings
from ps.models.api import Subject
from ps.models.enums import PaymentAction
from ps.models.payment import Payment


class PolicyDeniedError(Exception):
    pass


class OpaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.opa_url).rstrip("/")

    async def is_allowed(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> bool:
        payload: dict[str, Any] = {
            "input": {
                "action": action.value,
                "subject": subject.to_opa_subject(),
                "payment": payment.to_opa_payment(
                    instruction_end_date=instruction_end_date,
                    instruction_status=instruction_status,
                ),
            }
        }
        url = f"{self.base_url}/v1/data/payment/lifecycle/allow"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()

        return bool(body.get("result"))

    async def authorize(
        self,
        action: PaymentAction,
        subject: Subject,
        payment: Payment,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> None:
        if not await self.is_allowed(
            action,
            subject,
            payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
        ):
            raise PolicyDeniedError(
                f"OPA denied {action.value} for payment {payment.payment_id}"
            )
