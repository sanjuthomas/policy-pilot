from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from authz.ilm_client import IlmClient, InstructionNotFoundError
from authz.service_identity import ServiceIdentity


@pytest.mark.asyncio
async def test_ilm_get_instruction() -> None:
    client = IlmClient()
    response = httpx.Response(
        200,
        json={"status": "STANDING", "end_date": "2027-01-01"},
        request=httpx.Request("GET", "http://ilm.test/api/v1/instructions/i1"),
    )

    with patch("authz.service_identity.service_identity") as identity:
        identity.token = "svc-token"
        identity.session_id = "sess"
        with patch("httpx.AsyncClient") as client_cls:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.get = AsyncMock(return_value=response)
            client_cls.return_value = instance

            body = await client.get_instruction("i1")

    assert body["status"] == "STANDING"


@pytest.mark.asyncio
async def test_ilm_get_instruction_not_found() -> None:
    client = IlmClient()
    response = httpx.Response(
        404,
        request=httpx.Request("GET", "http://ilm.test/api/v1/instructions/missing"),
    )

    with patch("authz.service_identity.service_identity") as identity:
        identity.token = None
        with patch("httpx.AsyncClient") as client_cls:
            instance = MagicMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            instance.get = AsyncMock(return_value=response)
            client_cls.return_value = instance

            with pytest.raises(InstructionNotFoundError):
                await client.get_instruction("missing")


@pytest.mark.asyncio
async def test_service_identity_login_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from authz import service_identity as si_module

    monkeypatch.setattr(si_module.settings, "zitadel_service_pat", "pat")
    monkeypatch.setattr(si_module.settings, "service_user_id", "svc-payment")
    monkeypatch.setattr(si_module.settings, "service_user_password", "Password1!")
    monkeypatch.setattr(si_module.settings, "oidc_issuer_url", "http://localhost:8080")

    response = httpx.Response(
        200,
        json={"sessionId": "sid", "sessionToken": "stoken"},
        request=httpx.Request("POST", "http://zitadel/v2/sessions"),
    )

    identity = ServiceIdentity()
    with patch("httpx.AsyncClient") as client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.post = AsyncMock(return_value=response)
        client_cls.return_value = instance

        await identity.login()

    assert identity.token == "stoken"
    assert identity.session_id == "sid"
