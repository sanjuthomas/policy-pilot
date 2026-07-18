from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from authz_client.client import AuthzClient
from authz_client.errors import AuthzClientError, AuthzServiceUnavailable


def _mock_async_client(response: httpx.Response | Exception):
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    if isinstance(response, Exception):
        mock_client.post = AsyncMock(side_effect=response)
    else:
        mock_client.post = AsyncMock(return_value=response)
    return mock_client


@pytest.mark.asyncio
async def test_evaluate_instruction_success() -> None:
    client = AuthzClient("http://authz:8094/")
    response = httpx.Response(
        200,
        json={
            "allowed": True,
            "allow_basis": ["role gate"],
            "violations": [],
            "is_alert": False,
        },
        request=httpx.Request(
            "POST",
            "http://authz:8094/api/v1/authorization/instructions/evaluate",
        ),
    )

    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(response)
        decision = await client.evaluate_instruction(
            action="APPROVE",
            instruction={"instruction_id": "I-1"},
            account={"account_id": "A-1"},
            service_token="svc-token",
            service_session_id="svc-sess",
            user_token="user-token",
            user_session_id="user-sess",
            subject={"user_id": "ficc-300"},
        )

    assert decision.allowed is True
    assert decision.allow_basis == ["role gate"]
    assert decision.is_alert is False
    call = mock_cls.return_value.post.await_args
    assert call.kwargs["headers"]["Authorization"] == "Bearer svc-token"
    assert call.kwargs["headers"]["X-On-Behalf-Of"] == "user-token"
    assert call.kwargs["json"]["subject"]["user_id"] == "ficc-300"


@pytest.mark.asyncio
async def test_evaluate_instruction_requires_tokens() -> None:
    client = AuthzClient("http://authz:8094")
    with pytest.raises(AuthzClientError, match="service_token"):
        await client.evaluate_instruction(
            action="APPROVE",
            instruction={},
            account={},
            user_token="user-token",
        )
    with pytest.raises(AuthzClientError, match="user_token"):
        await client.evaluate_instruction(
            action="APPROVE",
            instruction={},
            account={},
            service_token="svc-token",
        )


@pytest.mark.asyncio
async def test_evaluate_payment_success_and_errors() -> None:
    client = AuthzClient("http://authz:8094")
    ok = httpx.Response(
        200,
        json={"allowed": False, "allow_basis": [], "violations": ["deny"], "is_alert": True},
        request=httpx.Request("POST", "http://authz:8094/x"),
    )

    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(ok)
        decision = await client.evaluate_payment(
            action="CREATE",
            payment={"payment_id": "P-1"},
            service_token="svc",
            user_token="user",
            subject={"user_id": "pay-101"},
        )
    assert decision.allowed is False
    assert decision.violations == ["deny"]
    assert decision.is_alert is True

    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(httpx.ConnectError("refused"))
        with pytest.raises(AuthzServiceUnavailable):
            await client.evaluate_payment(
                action="CREATE",
                payment={},
                service_token="svc",
                user_token="user",
            )

    bad = httpx.Response(
        503,
        text="down",
        request=httpx.Request("POST", "http://authz:8094/x"),
    )
    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(bad)
        with pytest.raises(AuthzServiceUnavailable):
            await client.evaluate_payment(
                action="CREATE",
                payment={},
                service_token="svc",
                user_token="user",
            )

    rejected = httpx.Response(
        403,
        text="forbidden",
        request=httpx.Request("POST", "http://authz:8094/x"),
    )
    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(rejected)
        with pytest.raises(AuthzClientError, match="rejected"):
            await client.evaluate_payment(
                action="CREATE",
                payment={},
                service_token="svc",
                user_token="user",
            )


@pytest.mark.asyncio
async def test_eligible_approvers() -> None:
    client = AuthzClient("http://authz:8094")
    response = httpx.Response(
        200,
        json={"approvers": [{"user_id": "pay-201"}]},
        request=httpx.Request("POST", "http://authz:8094/x"),
    )

    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(response)
        payment = await client.eligible_payment_approvers(
            payment={"payment_id": "P-1"},
            instruction_status="APPROVED",
            service_token="svc",
            service_session_id="sess",
            user_token="user-token",
            user_session_id="user-sess",
        )
        instruction = await client.eligible_instruction_approvers(
            instruction={"instruction_id": "I-1"},
            service_token="svc",
            user_token="user-token",
        )

    assert payment["approvers"][0]["user_id"] == "pay-201"
    assert instruction["approvers"][0]["user_id"] == "pay-201"


@pytest.mark.asyncio
async def test_post_json_error_paths() -> None:
    client = AuthzClient("http://authz:8094")

    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(httpx.ConnectError("refused"))
        with pytest.raises(AuthzServiceUnavailable):
            await client.eligible_payment_approvers(
                payment={},
                instruction_status="APPROVED",
                service_token="svc",
                user_token="user",
            )

    server = httpx.Response(500, text="err", request=httpx.Request("POST", "http://x"))
    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(server)
        with pytest.raises(AuthzServiceUnavailable):
            await client.eligible_instruction_approvers(
                instruction={},
                service_token="svc",
                user_token="user",
            )

    client_err = httpx.Response(400, text="bad", request=httpx.Request("POST", "http://x"))
    with patch("authz_client.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _mock_async_client(client_err)
        with pytest.raises(AuthzClientError):
            await client.eligible_instruction_approvers(
                instruction={},
                service_token="svc",
                user_token="user",
            )
