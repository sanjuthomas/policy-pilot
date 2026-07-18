from __future__ import annotations

from typing import Any

import httpx

from chat_application.auth.service_identity import service_identity
from chat_application.config import settings


class PaymentClientError(Exception):
    pass


class PaymentCreateDenied(PaymentClientError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PaymentSubmitDenied(PaymentClientError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PaymentApproveDenied(PaymentClientError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PaymentCancelDenied(PaymentClientError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PaymentNotFoundError(PaymentClientError):
    pass


class PaymentClient:
    """Payment reads/mutations via svc-chat + user OBO."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 30.0) -> None:
        self._base = (base_url or settings.payment_service_url).rstrip("/")
        self._timeout = timeout

    async def _obo_headers(
        self, *, user_token: str, user_session_id: str | None
    ) -> dict[str, str]:
        if not service_identity.token:
            await service_identity.ensure_logged_in()
        if not service_identity.token:
            raise PaymentClientError(
                "chat service identity not logged in — cannot call payment-service with OBO"
            )
        headers = {
            "Authorization": f"Bearer {service_identity.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-On-Behalf-Of": user_token,
        }
        if service_identity.session_id:
            headers["X-Session-Id"] = service_identity.session_id
        if user_session_id:
            headers["X-On-Behalf-Of-Session-Id"] = user_session_id
        return headers

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        detail = response.text
        try:
            detail = str(response.json().get("detail", detail))
        except Exception:
            pass
        return detail

    async def get_payment(
        self,
        payment_id: str,
        *,
        user_token: str,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        url = f"{self._base}/api/v1/payments/{payment_id}"
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
            raise PaymentClientError(
                f"payment-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 404:
            raise PaymentNotFoundError(f"payment {payment_id} not found")
        if response.status_code >= 400:
            raise PaymentClientError(
                f"payment-service rejected GET ({response.status_code}): "
                f"{self._detail(response)}"
            )
        return response.json()

    async def create_payment(
        self,
        *,
        instruction_id: str,
        amount: float,
        value_date: str,
        user_token: str,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        payload = {
            "instruction_id": instruction_id,
            "amount": amount,
            "value_date": value_date,
        }
        url = f"{self._base}/api/v1/payments"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=await self._obo_headers(
                        user_token=user_token,
                        user_session_id=user_session_id,
                    ),
                )
        except httpx.HTTPError as exc:
            raise PaymentClientError(
                f"payment-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 403:
            raise PaymentCreateDenied(self._detail(response))

        if response.status_code >= 400:
            raise PaymentClientError(
                f"payment-service rejected CREATE ({response.status_code}): "
                f"{self._detail(response)}"
            )
        return response.json()

    async def submit_payment(
        self,
        payment_id: str,
        *,
        user_token: str,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        url = f"{self._base}/api/v1/payments/{payment_id}/submit"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    headers=await self._obo_headers(
                        user_token=user_token,
                        user_session_id=user_session_id,
                    ),
                )
        except httpx.HTTPError as exc:
            raise PaymentClientError(
                f"payment-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 403:
            raise PaymentSubmitDenied(self._detail(response))
        if response.status_code == 404:
            raise PaymentNotFoundError(f"payment {payment_id} not found")
        if response.status_code >= 400:
            raise PaymentClientError(
                f"payment-service rejected SUBMIT ({response.status_code}): "
                f"{self._detail(response)}"
            )
        return response.json()

    async def approve_payment(
        self,
        payment_id: str,
        *,
        user_token: str,
        user_session_id: str | None,
    ) -> dict[str, Any]:
        url = f"{self._base}/api/v1/payments/{payment_id}/approve"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    headers=await self._obo_headers(
                        user_token=user_token,
                        user_session_id=user_session_id,
                    ),
                )
        except httpx.HTTPError as exc:
            raise PaymentClientError(
                f"payment-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 403:
            raise PaymentApproveDenied(self._detail(response))
        if response.status_code == 404:
            raise PaymentNotFoundError(f"payment {payment_id} not found")
        if response.status_code >= 400:
            raise PaymentClientError(
                f"payment-service rejected APPROVE ({response.status_code}): "
                f"{self._detail(response)}"
            )
        return response.json()

    async def cancel_payment(
        self,
        payment_id: str,
        *,
        user_token: str,
        user_session_id: str | None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base}/api/v1/payments/{payment_id}/cancel"
        payload = {"reason": reason} if reason else {}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=await self._obo_headers(
                        user_token=user_token,
                        user_session_id=user_session_id,
                    ),
                )
        except httpx.HTTPError as exc:
            raise PaymentClientError(
                f"payment-service unreachable at {self._base}"
            ) from exc

        if response.status_code == 403:
            raise PaymentCancelDenied(self._detail(response))
        if response.status_code == 404:
            raise PaymentNotFoundError(f"payment {payment_id} not found")
        if response.status_code >= 400:
            raise PaymentClientError(
                f"payment-service rejected CANCEL ({response.status_code}): "
                f"{self._detail(response)}"
            )
        return response.json()
