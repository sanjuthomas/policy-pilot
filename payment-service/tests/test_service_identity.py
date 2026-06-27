from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from ps import database
from ps.service_identity import ServiceIdentity, _host_header, _zitadel_base


def test_get_db_raises_when_not_connected() -> None:
    with patch.object(database, "_client", None):
        with pytest.raises(RuntimeError, match="MongoDB not connected"):
            database.get_db()


def test_get_security_events_db_raises_when_not_connected() -> None:
    with patch.object(database, "_client", None):
        with pytest.raises(RuntimeError, match="MongoDB not connected"):
            database.get_security_events_db()


@pytest.mark.asyncio
async def test_connect_and_close() -> None:
    mock_client = MagicMock()
    with patch("ps.database.AsyncIOMotorClient", return_value=mock_client):
        await database.connect()
        assert database._client is mock_client
        await database.close()
        assert database._client is None
        mock_client.close.assert_called_once()


def test_zitadel_base_from_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.service_identity.settings.zitadel_internal_url", None)
    monkeypatch.setattr("ps.service_identity.settings.oidc_internal_url", None)
    monkeypatch.setattr("ps.service_identity.settings.oidc_issuer_url", "https://auth.example.com/")
    assert _zitadel_base() == "https://auth.example.com"


def test_zitadel_base_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.service_identity.settings.zitadel_internal_url", None)
    monkeypatch.setattr("ps.service_identity.settings.oidc_internal_url", None)
    monkeypatch.setattr("ps.service_identity.settings.oidc_issuer_url", None)
    with pytest.raises(RuntimeError, match="No Zitadel URL"):
        _zitadel_base()


def test_host_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ps.service_identity.settings.oidc_issuer_url",
        "https://auth.example.com:443",
    )
    assert _host_header() == {"Host": "auth.example.com"}


@pytest.mark.asyncio
async def test_login_skips_without_pat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.service_identity.settings.zitadel_service_pat", None)
    identity = ServiceIdentity()
    await identity.login()
    assert identity.token is None


@pytest.mark.asyncio
async def test_login_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.service_identity.settings.zitadel_service_pat", "pat")
    monkeypatch.setattr("ps.service_identity.settings.oidc_issuer_url", "https://auth.example.com")
    monkeypatch.setattr("ps.service_identity.settings.service_user_id", "svc-payment")
    monkeypatch.setattr("ps.service_identity.settings.service_user_password", "Password1!")

    mock_response = httpx.Response(
        200,
        json={"sessionId": "sess-1", "sessionToken": "tok-1"},
        request=httpx.Request("POST", "https://auth.example.com/v2/sessions"),
    )

    with patch("ps.service_identity.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        identity = ServiceIdentity()
        await identity.login()

    assert identity.token == "tok-1"
    assert identity.session_id == "sess-1"


@pytest.mark.asyncio
async def test_login_failure_clears_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.service_identity.settings.zitadel_service_pat", "pat")
    monkeypatch.setattr("ps.service_identity.settings.oidc_issuer_url", "https://auth.example.com")

    with patch("ps.service_identity.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(side_effect=RuntimeError("network"))
        mock_client_cls.return_value = mock_client

        identity = ServiceIdentity()
        await identity.login(max_attempts=1)

    assert identity.token is None
    assert identity.session_id is None


@pytest.mark.asyncio
async def test_login_retries_before_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.service_identity.settings.zitadel_service_pat", "pat")
    monkeypatch.setattr("ps.service_identity.settings.oidc_issuer_url", "https://auth.example.com")
    monkeypatch.setattr("ps.service_identity.settings.service_user_id", "svc-payment")
    monkeypatch.setattr("ps.service_identity.settings.service_user_password", "Password1!")

    success_response = httpx.Response(
        200,
        json={"sessionId": "sess-1", "sessionToken": "tok-1"},
        request=httpx.Request("POST", "https://auth.example.com/v2/sessions"),
    )

    with patch("ps.service_identity.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(
            side_effect=[RuntimeError("network"), success_response],
        )
        mock_client_cls.return_value = mock_client

        identity = ServiceIdentity()
        await identity.login(max_attempts=2, retry_delay_s=0)

    assert identity.token == "tok-1"
    assert mock_client.post.await_count == 2
