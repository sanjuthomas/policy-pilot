from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from chat_application.auth.service_identity import (
    ServiceIdentity,
    _host_header,
    _zitadel_base,
)
from chat_application.auth.zitadel import ZitadelAuthClient, login_name_for_user


def _context(response=None, error=None):
    client = MagicMock()
    client.post = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    return context, client


def _response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("POST", "http://zitadel.test/v2/sessions"),
    )


def test_login_name_and_request_headers() -> None:
    assert login_name_for_user("user") == "user@ssi.local"
    assert login_name_for_user("user@example.test") == "user@example.test"
    client = ZitadelAuthClient(
        "http://zitadel.test/", "pat", host_header="issuer.example.test"
    )
    assert client._request_headers()["Host"] == "issuer.example.test"


@pytest.mark.asyncio
async def test_zitadel_login_retries_short_username_after_status_error() -> None:
    first = _response(401, {})
    second = _response(200, {"session_id": "s1", "session_token": "t1"})
    context, mock_client = _context()
    mock_client.post = AsyncMock(side_effect=[first, second])
    first.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "bad credentials", request=first.request, response=first
    ))

    with patch("chat_application.auth.zitadel.httpx.AsyncClient", return_value=context):
        credentials = await ZitadelAuthClient("http://zitadel.test", "pat").login(
            "user@example.test", "password"
        )

    assert credentials.session_id == "s1"
    assert credentials.user_id == "user"
    assert mock_client.post.await_args_list[1].kwargs["json"]["checks"]["user"] == {
        "loginName": "user"
    }


@pytest.mark.asyncio
async def test_zitadel_session_requires_both_session_fields() -> None:
    response = _response(200, {"sessionId": "s1"})
    context, _ = _context(response)
    with (
        patch("chat_application.auth.zitadel.httpx.AsyncClient", return_value=context),
        pytest.raises(RuntimeError, match="missing session fields"),
    ):
        await ZitadelAuthClient("http://zitadel.test", "pat").login("user", "password")


@pytest.mark.asyncio
async def test_zitadel_login_reraises_last_status_error() -> None:
    response = _response(401, {})
    response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "bad credentials", request=response.request, response=response
        )
    )
    context, _ = _context(response)
    with (
        patch("chat_application.auth.zitadel.httpx.AsyncClient", return_value=context),
        pytest.raises(httpx.HTTPStatusError, match="bad credentials"),
    ):
        await ZitadelAuthClient("http://zitadel.test", "pat").login("user", "password")


def test_service_identity_url_and_host_helpers() -> None:
    with patch("chat_application.auth.service_identity.settings") as settings:
        settings.zitadel_internal_url = "http://internal/"
        settings.oidc_internal_url = "http://oidc-internal"
        settings.oidc_issuer_url = "https://issuer.example.test/path"
        assert _zitadel_base() == "http://internal"
        assert _host_header() == {"Host": "issuer.example.test"}
        settings.zitadel_internal_url = ""
        settings.oidc_internal_url = ""
        settings.oidc_issuer_url = ""
        with pytest.raises(RuntimeError, match="No Zitadel URL"):
            _zitadel_base()
        assert _host_header() == {}


@pytest.mark.asyncio
async def test_service_identity_login_handles_unconfigured_success_and_failure() -> None:
    identity = ServiceIdentity()
    with patch("chat_application.auth.service_identity.settings") as settings:
        settings.zitadel_service_pat = ""
        await identity.login()
        assert identity.token is None

    response = _response(200, {"sessionId": "s1", "sessionToken": "t1"})
    context, _ = _context(response)
    with (
        patch("chat_application.auth.service_identity.settings") as settings,
        patch("chat_application.auth.service_identity.httpx.AsyncClient", return_value=context),
    ):
        settings.zitadel_service_pat = "pat"
        settings.service_user_id = "svc-chat"
        settings.service_user_password = "password"
        settings.zitadel_internal_url = "http://zitadel.test"
        settings.oidc_internal_url = ""
        settings.oidc_issuer_url = ""
        await identity.login(max_attempts=1)
    assert identity.session_id == "s1"
    assert identity.token == "t1"

    context, _ = _context(error=httpx.ConnectError("down"))
    with (
        patch("chat_application.auth.service_identity.settings") as settings,
        patch("chat_application.auth.service_identity.httpx.AsyncClient", return_value=context),
    ):
        settings.zitadel_service_pat = "pat"
        settings.service_user_id = "svc-chat"
        settings.service_user_password = "password"
        settings.zitadel_internal_url = "http://zitadel.test"
        settings.oidc_internal_url = ""
        settings.oidc_issuer_url = ""
        await identity.login(max_attempts=1)
    assert identity.token is None
    assert identity.session_id is None
