from unittest.mock import AsyncMock, patch

import httpx
import pytest

from chat_application.authz.client import (
    EligibilityClient,
    EligibilityClientError,
)


@pytest.mark.asyncio
async def test_eligible_approvers_for_payment_success() -> None:
    response = httpx.Response(
        200,
        json={"payment_id": "p1", "eligible": []},
        request=httpx.Request("POST", "http://payment.test/api/v1/payments/p1/eligible-approvers"),
    )

    with (
        patch("chat_application.authz.client.httpx.AsyncClient") as mock_client_cls,
        patch("chat_application.authz.client.service_identity") as mock_identity,
    ):
        mock_identity.token = "svc-token"
        mock_identity.session_id = "svc-session"
        mock_identity.ensure_logged_in = AsyncMock()
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.post = AsyncMock(return_value=response)
        client = EligibilityClient(
            payment_service_url="http://payment.test",
            instruction_service_url="http://instruction.test",
        )
        body = await client.eligible_approvers_for_payment(
            "p1",
            bearer_token="user-token",
            session_id="user-session",
        )

    assert body["payment_id"] == "p1"
    headers = mock_client.post.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer svc-token"
    assert headers["X-On-Behalf-Of"] == "user-token"
    assert headers["X-On-Behalf-Of-Session-Id"] == "user-session"
    assert headers["X-Session-Id"] == "svc-session"


@pytest.mark.asyncio
async def test_eligible_approvers_for_payment_forbidden() -> None:
    response = httpx.Response(
        403,
        json={"detail": "forbidden"},
        request=httpx.Request("POST", "http://payment.test/api/v1/payments/p1/eligible-approvers"),
    )

    with (
        patch("chat_application.authz.client.httpx.AsyncClient") as mock_client_cls,
        patch("chat_application.authz.client.service_identity") as mock_identity,
    ):
        mock_identity.token = None
        mock_identity.session_id = None
        mock_identity.ensure_logged_in = AsyncMock()
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.post = AsyncMock(return_value=response)
        client = EligibilityClient(payment_service_url="http://payment.test")

        with pytest.raises(EligibilityClientError, match="not logged in"):
            await client.eligible_approvers_for_payment("p1", bearer_token="token")


@pytest.mark.asyncio
async def test_policy_summary_success() -> None:
    response = httpx.Response(
        200,
        json={
            "domain": "payment",
            "action": "APPROVE",
            "title": "Funding approval",
            "narrative": "Someone with FUNDING_APPROVER…",
            "requires": [{"kind": "role", "value": "FUNDING_APPROVER"}],
            "source": "opa",
        },
        request=httpx.Request(
            "GET",
            "http://authz.test/api/v1/authorization/policy-summary",
        ),
    )

    with (
        patch("chat_application.authz.client.httpx.AsyncClient") as mock_client_cls,
        patch("chat_application.authz.client.service_identity") as mock_identity,
    ):
        mock_identity.token = "svc-token"
        mock_identity.session_id = "svc-session"
        mock_identity.ensure_logged_in = AsyncMock()
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get = AsyncMock(return_value=response)
        client = EligibilityClient(authorization_service_url="http://authz.test")
        body = await client.policy_summary(
            domain="payment",
            action="APPROVE",
            bearer_token="token",
            session_id="sess-1",
        )

    assert body["title"] == "Funding approval"
    mock_client.get.assert_awaited_once()
    call_kwargs = mock_client.get.await_args.kwargs
    assert call_kwargs["params"] == {"domain": "payment", "action": "APPROVE"}
    assert call_kwargs["headers"]["Authorization"] == "Bearer svc-token"
    assert call_kwargs["headers"]["X-On-Behalf-Of"] == "token"
    assert call_kwargs["headers"]["X-On-Behalf-Of-Session-Id"] == "sess-1"


@pytest.mark.asyncio
async def test_payment_amount_limits_success() -> None:
    response = httpx.Response(
        200,
        json={
            "absolute_limit": 100_000_000_000.0,
            "club_limits": {"UP_TO_100_BILLION_CLUB": 100_000_000_000.0},
            "source": "opa",
        },
        request=httpx.Request(
            "GET",
            "http://authz.test/api/v1/authorization/payment-amount-limits",
        ),
    )

    with (
        patch("chat_application.authz.client.httpx.AsyncClient") as mock_client_cls,
        patch("chat_application.authz.client.service_identity") as mock_identity,
    ):
        mock_identity.token = "svc-token"
        mock_identity.session_id = "svc-session"
        mock_identity.ensure_logged_in = AsyncMock()
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get = AsyncMock(return_value=response)
        client = EligibilityClient(authorization_service_url="http://authz.test")
        body = await client.payment_amount_limits(
            bearer_token="token",
            session_id="sess-1",
        )

    assert body["absolute_limit"] == 100_000_000_000.0
    assert "UP_TO_100_BILLION_CLUB" in body["club_limits"]
    call_kwargs = mock_client.get.await_args.kwargs
    assert call_kwargs["headers"]["X-On-Behalf-Of"] == "token"
    assert call_kwargs["headers"]["X-On-Behalf-Of-Session-Id"] == "sess-1"
