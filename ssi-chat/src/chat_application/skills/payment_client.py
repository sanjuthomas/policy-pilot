from __future__ import annotations

from typing import Any

import httpx

from chat_application.config import settings


class PaymentClientError(Exception):
    pass


class PaymentCreateDenied(PaymentClientError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PaymentClient:
    """Create draft payments as the logged-in chat user."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 30.0) -> None:
        self._base = (base_url or settings.payment_service_url).rstrip("/")
        self._timeout = timeout

    async def create_payment(
        self,
        *,
        instruction_id: str,
        amount: float,
        value_date: str,
        user_token: str,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if user_session_id:
            headers["X-Session-Id"] = user_session_id

        payload = {
            "instruction_id": instruction_id,
            "amount": amount,
            "value_date": value_date,
        }
        url = f"{self._base}/api/v1/payments"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise PaymentClientError(
                f"payment-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 403:
            detail = response.text
            try:
                detail = str(response.json().get("detail", detail))
            except Exception:
                pass
            raise PaymentCreateDenied(detail)

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = str(response.json().get("detail", detail))
            except Exception:
                pass
            raise PaymentClientError(
                f"payment-service rejected CREATE ({response.status_code}): {detail}"
            )
        return response.json()
