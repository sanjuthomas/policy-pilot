from __future__ import annotations

from typing import Any

import httpx

from harness.config import Settings
from harness.zitadel_auth import SessionCredentials


class PaymentServiceClient:
    """Thin synchronous HTTP client over the Payment Service REST API."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.payment_service_url.rstrip("/")
        self.api_prefix = settings.payment_service_api_prefix.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.api_prefix}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        session: SessionCredentials,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        with httpx.Client(timeout=30.0) as client:
            return client.request(
                method,
                self._url(path),
                headers={
                    "Authorization": f"Bearer {session.session_token}",
                    "X-Session-Id": session.session_id,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=json_body,
            )

    def create_payment(
        self,
        session: SessionCredentials,
        instruction_id: str,
        amount: float,
        value_date: str,
    ) -> httpx.Response:
        return self.request(
            "POST",
            "/payments",
            session=session,
            json_body={
                "instruction_id": instruction_id,
                "amount": amount,
                "value_date": value_date,
            },
        )

    def submit_payment(
        self, session: SessionCredentials, payment_id: str
    ) -> httpx.Response:
        return self.request("POST", f"/payments/{payment_id}/submit", session=session)

    def approve_payment(
        self, session: SessionCredentials, payment_id: str
    ) -> httpx.Response:
        return self.request("POST", f"/payments/{payment_id}/approve", session=session)

    def reject_payment(
        self,
        session: SessionCredentials,
        payment_id: str,
        *,
        reason: str,
    ) -> httpx.Response:
        return self.request(
            "POST",
            f"/payments/{payment_id}/reject",
            session=session,
            json_body={"reason": reason},
        )

    def get_payment(
        self, session: SessionCredentials, payment_id: str
    ) -> httpx.Response:
        return self.request("GET", f"/payments/{payment_id}", session=session)

    def list_payments(
        self,
        session: SessionCredentials,
        *,
        status: str | None = None,
        limit: int = 500,
    ) -> httpx.Response:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        url = self._url("/payments")
        with httpx.Client(timeout=30.0) as client:
            return client.get(
                url,
                headers={
                    "Authorization": f"Bearer {session.session_token}",
                    "X-Session-Id": session.session_id,
                    "Accept": "application/json",
                },
                params=params,
            )

    def update_payment(
        self,
        session: SessionCredentials,
        payment_id: str,
        instruction_id: str,
        amount: float,
        value_date: str,
    ) -> httpx.Response:
        return self.request(
            "PUT",
            f"/payments/{payment_id}",
            session=session,
            json_body={
                "instruction_id": instruction_id,
                "amount": amount,
                "value_date": value_date,
            },
        )
