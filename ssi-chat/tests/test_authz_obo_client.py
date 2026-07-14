from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from chat_application.authz.obo import AuthzOboClient, AuthzOboClientError


@pytest.mark.asyncio
async def test_evaluate_payment_obo_success() -> None:
    client = AuthzOboClient(base_url="http://authz.test")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "allowed": True,
        "allow_basis": ["catalog_role_ok"],
        "violations": [],
        "is_alert": False,
    }
    response.is_success = True

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("chat_application.authz.obo.httpx.AsyncClient", return_value=mock_client):
        decision = await client.evaluate_payment(
            action="APPROVE",
            payment={"payment_id": "p1", "amount": 1.0},
            service_token="svc-token",
            service_session_id="svc-sid",
            user_token="user-token",
            user_session_id="user-sid",
        )

    assert decision.allowed is True
    kwargs = mock_client.post.await_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer svc-token"
    assert kwargs["headers"]["X-On-Behalf-Of"] == "user-token"
    assert kwargs["headers"]["X-On-Behalf-Of-Session-Id"] == "user-sid"


@pytest.mark.asyncio
async def test_evaluate_payment_requires_service_token() -> None:
    client = AuthzOboClient(base_url="http://authz.test")
    with pytest.raises(AuthzOboClientError, match="service token"):
        await client.evaluate_payment(
            action="APPROVE",
            payment={},
            user_token="user-token",
        )


@pytest.mark.asyncio
async def test_evaluate_payment_inline_subject() -> None:
    client = AuthzOboClient(base_url="http://authz.test")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "allowed": False,
        "allow_basis": [],
        "violations": ["missing role"],
        "is_alert": False,
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("chat_application.authz.obo.httpx.AsyncClient", return_value=mock_client):
        decision = await client.evaluate_payment(
            action="CREATE",
            payment={"amount": 10},
            service_token="svc-token",
            subject={"user_id": "pay-101", "roles": ["PAYMENT_CREATOR"]},
        )

    assert decision.allowed is False
    assert mock_client.post.await_args.kwargs["json"]["subject"]["user_id"] == "pay-101"


@pytest.mark.asyncio
async def test_evaluate_payment_http_error() -> None:
    client = AuthzOboClient(base_url="http://authz.test")
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("chat_application.authz.obo.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthzOboClientError, match="unreachable"):
            await client.evaluate_payment(
                action="APPROVE",
                payment={},
                service_token="svc",
                user_token="user",
            )
