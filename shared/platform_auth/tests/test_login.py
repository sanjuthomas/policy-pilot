from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from platform_auth.login import LoginRequest, ZitadelLoginClient


def test_login_request_validation() -> None:
    request = LoginRequest(user_id="admin-001", password="Password1!")
    assert request.user_id == "admin-001"


def test_login_success() -> None:
    client = ZitadelLoginClient("http://zitadel", "pat-token", host_header="localhost")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "sessionId": "sess-1",
        "sessionToken": "token-1",
    }

    with patch("platform_auth.login.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = response
        mock_client_cls.return_value = mock_client

        session = client.login("admin-001", "Password1!")

    assert session.user_id == "admin-001"
    assert session.session_id == "sess-1"
    assert session.session_token == "token-1"
    headers = mock_client.post.call_args.kwargs["headers"]
    assert headers["Host"] == "localhost"


def test_login_strips_email_domain_on_retry() -> None:
    client = ZitadelLoginClient("http://zitadel", "pat-token")
    ok_response = MagicMock()
    ok_response.raise_for_status = MagicMock()
    ok_response.json.return_value = {
        "session_id": "sess-2",
        "session_token": "token-2",
    }
    fail_response = MagicMock()
    fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404",
        request=MagicMock(),
        response=MagicMock(status_code=404),
    )

    with patch("platform_auth.login.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = [fail_response, ok_response]
        mock_client_cls.return_value = mock_client

        session = client.login("admin-001@ssi.local", "Password1!")

    assert session.session_id == "sess-2"
    assert mock_client.post.call_count == 2


def test_login_missing_session_fields_raises() -> None:
    client = ZitadelLoginClient("http://zitadel", "pat-token")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"sessionId": "only-id"}

    with patch("platform_auth.login.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = response
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="missing session fields"):
            client.login("admin-001", "Password1!")


def test_login_propagates_http_error() -> None:
    client = ZitadelLoginClient("http://zitadel", "pat-token")
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401",
        request=MagicMock(),
        response=MagicMock(status_code=401),
    )

    with patch("platform_auth.login.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = response
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            client.login("admin-001", "Password1!")
