from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from chat_application.authorization_client import AuthorizationClient, AuthorizationClientError


@pytest.mark.asyncio
async def test_eligible_approvers_for_payment_success() -> None:
    client = AuthorizationClient(base_url="http://authz.test")
    response = httpx.Response(
        200,
        json={"payment_id": "p1", "eligible": []},
        request=httpx.Request("POST", "http://authz.test/api/v1/payments/p1/eligible-approvers"),
    )

    with patch("httpx.AsyncClient") as client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(return_value=response)
        client_cls.return_value = instance

        body = await client.eligible_approvers_for_payment(
            "p1",
            bearer_token="token",
            session_id="sess",
        )

    assert body["payment_id"] == "p1"


@pytest.mark.asyncio
async def test_eligible_approvers_for_payment_forbidden() -> None:
    client = AuthorizationClient(base_url="http://authz.test")
    response = httpx.Response(
        403,
        json={"detail": "forbidden"},
        request=httpx.Request("POST", "http://authz.test/api/v1/payments/p1/eligible-approvers"),
    )

    with patch("httpx.AsyncClient") as client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(return_value=response)
        client_cls.return_value = instance

        with pytest.raises(AuthorizationClientError, match="COMPLIANCE_ANALYST"):
            await client.eligible_approvers_for_payment("p1", bearer_token="token")
