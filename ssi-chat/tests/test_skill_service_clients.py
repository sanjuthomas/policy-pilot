from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from chat_application.skills.instruction_client import (
    InstructionClient,
    InstructionClientError,
    InstructionNotFoundError,
)
from chat_application.skills.payment_client import (
    PaymentCancelDenied,
    PaymentClient,
    PaymentClientError,
    PaymentCreateDenied,
    PaymentNotFoundError,
)


def _response(status_code: int, *, json=None, text="error") -> httpx.Response:
    return httpx.Response(
        status_code,
        json=json,
        text=None if json is not None else text,
        request=httpx.Request("GET", "http://service.test"),
    )


def _async_client(response=None, error=None):
    client = MagicMock()
    method = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    client.get = method
    client.post = method
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    return context, client


def test_instruction_headers_use_service_obo_or_user_identity() -> None:
    client = InstructionClient("http://instruction.test")
    with patch("chat_application.skills.instruction_client.service_identity") as identity:
        identity.token = "service-token"
        identity.session_id = "service-session"
        assert client._headers(user_token="user-token", user_session_id="user-session") == {
            "Authorization": "Bearer service-token",
            "Accept": "application/json",
            "X-On-Behalf-Of": "user-token",
            "X-Session-Id": "service-session",
            "X-On-Behalf-Of-Session-Id": "user-session",
        }
        identity.token = None
        assert client._headers(user_token="user-token", user_session_id="user-session") == {
            "Accept": "application/json",
            "Authorization": "Bearer user-token",
            "X-Session-Id": "user-session",
        }


@pytest.mark.asyncio
async def test_instruction_client_success_and_errors() -> None:
    context, mock_client = _async_client(_response(200, json={"instruction_id": "i1"}))
    with patch("chat_application.skills.instruction_client.httpx.AsyncClient", return_value=context):
        result = await InstructionClient("http://instruction.test").get_instruction(
            "i1", user_token=None, user_session_id=None
        )
    assert result == {"instruction_id": "i1"}
    assert mock_client.get.await_args.args[0].endswith("/i1")

    for response, expected in [
        (_response(404), InstructionNotFoundError),
        (_response(500, json={"detail": "broken"}), InstructionClientError),
    ]:
        context, _ = _async_client(response)
        with (
            patch(
                "chat_application.skills.instruction_client.httpx.AsyncClient",
                return_value=context,
            ),
            pytest.raises(expected),
        ):
            await InstructionClient("http://instruction.test").get_instruction(
                "i1", user_token=None, user_session_id=None
            )

    context, _ = _async_client(error=httpx.ConnectError("down"))
    with (
        patch(
            "chat_application.skills.instruction_client.httpx.AsyncClient",
            return_value=context,
        ),
        pytest.raises(InstructionClientError, match="unreachable"),
    ):
        await InstructionClient("http://instruction.test").get_instruction(
            "i1", user_token=None, user_session_id=None
        )


@pytest.mark.asyncio
async def test_payment_client_success_denied_and_errors() -> None:
    context, mock_client = _async_client(_response(201, json={"payment_id": "p1"}))
    with patch("chat_application.skills.payment_client.httpx.AsyncClient", return_value=context):
        result = await PaymentClient("http://payment.test").create_payment(
            instruction_id="i1",
            amount=12.0,
            value_date="2026-01-01",
            user_token="token",
            user_session_id="session",
        )
    assert result == {"payment_id": "p1"}
    assert mock_client.post.await_args.kwargs["headers"]["X-Session-Id"] == "session"

    for response, expected in [
        (_response(403, json={"detail": "not allowed"}), PaymentCreateDenied),
        (_response(422, text="invalid"), PaymentClientError),
    ]:
        context, _ = _async_client(response)
        with (
            patch(
                "chat_application.skills.payment_client.httpx.AsyncClient",
                return_value=context,
            ),
            pytest.raises(expected),
        ):
            await PaymentClient("http://payment.test").create_payment(
                instruction_id="i1",
                amount=12.0,
                value_date="2026-01-01",
                user_token="token",
                user_session_id=None,
            )

    context, _ = _async_client(error=httpx.ConnectError("down"))
    with (
        patch(
            "chat_application.skills.payment_client.httpx.AsyncClient",
            return_value=context,
        ),
        pytest.raises(PaymentClientError, match="unreachable"),
    ):
        await PaymentClient("http://payment.test").create_payment(
            instruction_id="i1",
            amount=12.0,
            value_date="2026-01-01",
            user_token="token",
            user_session_id=None,
        )


@pytest.mark.asyncio
async def test_payment_client_cancel_success_denied_and_errors() -> None:
    context, mock_client = _async_client(
        _response(200, json={"payment_id": "p1", "status": "CANCELLED"})
    )
    with patch(
        "chat_application.skills.payment_client.httpx.AsyncClient", return_value=context
    ):
        result = await PaymentClient("http://payment.test").cancel_payment(
            "p1",
            user_token="token",
            user_session_id="session",
            reason="demo",
        )
    assert result["status"] == "CANCELLED"
    assert mock_client.post.await_args.args[0].endswith("/p1/cancel")
    assert mock_client.post.await_args.kwargs["json"] == {"reason": "demo"}

    for response, expected in [
        (_response(403, json={"detail": "not allowed"}), PaymentCancelDenied),
        (_response(404), PaymentNotFoundError),
        (_response(422, text="invalid"), PaymentClientError),
    ]:
        context, _ = _async_client(response)
        with (
            patch(
                "chat_application.skills.payment_client.httpx.AsyncClient",
                return_value=context,
            ),
            pytest.raises(expected),
        ):
            await PaymentClient("http://payment.test").cancel_payment(
                "p1",
                user_token="token",
                user_session_id=None,
            )

    context, _ = _async_client(error=httpx.ConnectError("down"))
    with (
        patch(
            "chat_application.skills.payment_client.httpx.AsyncClient",
            return_value=context,
        ),
        pytest.raises(PaymentClientError, match="unreachable"),
    ):
        await PaymentClient("http://payment.test").cancel_payment(
            "p1",
            user_token="token",
            user_session_id=None,
        )
