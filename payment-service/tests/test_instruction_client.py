from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from ps.instruction_client import (
    InstructionNotFoundError,
    InstructionServiceClient,
    InstructionStateError,
)

_REQUEST = httpx.Request("GET", "http://instruction-service.test/api/v1/instructions/i1")
_POST_REQUEST = httpx.Request("POST", "http://instruction-service.test/api/v1/instructions/i1/use")


@pytest.fixture
def instruction_service_client() -> InstructionServiceClient:
    return InstructionServiceClient()


@pytest.mark.asyncio
async def test_auth_headers_obo_delegation(
    instruction_service_client: InstructionServiceClient,
) -> None:
    service_identity = MagicMock()
    service_identity.token = "svc-token"
    service_identity.session_id = "svc-session"
    service_identity.ensure_logged_in = AsyncMock()

    with patch("ps.service_identity.service_identity", service_identity):
        headers = await instruction_service_client._auth_headers("user-token", "user-session")

    assert headers["Authorization"] == "Bearer svc-token"
    assert headers["X-Session-Id"] == "svc-session"
    assert headers["X-On-Behalf-Of"] == "user-token"
    assert headers["X-On-Behalf-Of-Session-Id"] == "user-session"
    service_identity.ensure_logged_in.assert_not_called()


@pytest.mark.asyncio
async def test_auth_headers_retries_login_when_service_token_missing(
    instruction_service_client: InstructionServiceClient,
) -> None:
    service_identity = MagicMock()
    service_identity.token = None
    service_identity.ensure_logged_in = AsyncMock()

    with patch("ps.service_identity.service_identity", service_identity):
        headers = await instruction_service_client._auth_headers("user-token", "user-session")

    service_identity.ensure_logged_in.assert_awaited_once()
    assert headers["Authorization"] == "Bearer user-token"
    assert headers["X-Session-Id"] == "user-session"


@pytest.mark.asyncio
async def test_auth_headers_fallback_user_token(
    instruction_service_client: InstructionServiceClient,
) -> None:
    service_identity = MagicMock()
    service_identity.token = None
    service_identity.ensure_logged_in = AsyncMock()

    with patch("ps.service_identity.service_identity", service_identity):
        headers = await instruction_service_client._auth_headers("user-token", "user-session")

    assert headers["Authorization"] == "Bearer user-token"
    assert headers["X-Session-Id"] == "user-session"


@pytest.mark.asyncio
async def test_get_instruction_success(
    instruction_service_client: InstructionServiceClient,
) -> None:
    payload = {"instruction_id": "i1", "status": "APPROVED"}
    mock_response = httpx.Response(200, json=payload, request=_REQUEST)

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await instruction_service_client.get_instruction("i1", bearer_token="tok")

    assert result == payload


@pytest.mark.asyncio
async def test_get_instruction_not_found(
    instruction_service_client: InstructionServiceClient,
) -> None:
    mock_response = httpx.Response(404, request=_REQUEST)

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(InstructionNotFoundError):
            await instruction_service_client.get_instruction("missing")


@pytest.mark.asyncio
async def test_mark_used_success(
    instruction_service_client: InstructionServiceClient,
) -> None:
    payload = {"status": "USED"}
    mock_response = httpx.Response(200, json=payload, request=_POST_REQUEST)

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await instruction_service_client.mark_used("i1", "pay-1")

    assert result == payload


@pytest.mark.asyncio
async def test_mark_used_conflict(
    instruction_service_client: InstructionServiceClient,
) -> None:
    mock_response = httpx.Response(409, text="already used", request=_POST_REQUEST)

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(InstructionStateError):
            await instruction_service_client.mark_used("i1", "pay-1")


@pytest.mark.asyncio
async def test_release_use_success(
    instruction_service_client: InstructionServiceClient,
) -> None:
    payload = {"status": "APPROVED", "used_by": None}
    request = httpx.Request(
        "POST",
        "http://instruction-service.test/api/v1/instructions/i1/release-use",
    )
    mock_response = httpx.Response(200, json=payload, request=request)

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await instruction_service_client.release_use("i1", "pay-1")

    assert result == payload


@pytest.mark.asyncio
async def test_get_instruction_as_service_success(
    instruction_service_client: InstructionServiceClient,
) -> None:
    payload = {"instruction_id": "i1", "status": "APPROVED"}
    mock_response = httpx.Response(200, json=payload, request=_REQUEST)
    service_identity = MagicMock()
    service_identity.token = "svc-token"
    service_identity.session_id = "svc-session"
    service_identity.ensure_logged_in = AsyncMock()

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls, patch(
        "ps.service_identity.service_identity", service_identity
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await instruction_service_client.get_instruction_as_service("i1")

    assert result == payload


@pytest.mark.asyncio
async def test_get_instruction_as_service_not_found(
    instruction_service_client: InstructionServiceClient,
) -> None:
    mock_response = httpx.Response(404, request=_REQUEST)
    service_identity = MagicMock()
    service_identity.token = "svc-token"
    service_identity.session_id = "svc-session"
    service_identity.ensure_logged_in = AsyncMock()

    with patch("ps.instruction_client.httpx.AsyncClient") as mock_client_cls, patch(
        "ps.service_identity.service_identity", service_identity
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(InstructionNotFoundError):
            await instruction_service_client.get_instruction_as_service("missing")
