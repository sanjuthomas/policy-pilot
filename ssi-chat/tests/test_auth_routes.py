from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from chat_application.auth.users import SeedFile, SeedUser
from chat_application.auth.zitadel import SessionCredentials


def _comp_seed() -> SeedFile:
    return SeedFile(
        defaults={"email_domain": "ssi.local"},
        users=[
            SeedUser(
                user_id="comp-001",
                given_name="Alex",
                family_name="Morgan",
                title="Compliance Analyst",
                roles=["COMPLIANCE_ANALYST"],
            )
        ],
    )


def _chat_seed() -> SeedFile:
    return SeedFile(
        defaults={"email_domain": "ssi.local"},
        users=[
            SeedUser(
                user_id="comp-001",
                given_name="Alex",
                family_name="Morgan",
                title="Compliance Analyst",
                roles=["COMPLIANCE_ANALYST"],
            ),
            SeedUser(
                user_id="pay-101",
                given_name="Mina",
                family_name="Okonkwo",
                title="Payment Ops",
                roles=["PAYMENT_CREATOR"],
            ),
        ],
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, test_client: TestClient) -> TestClient:
    monkeypatch.setattr(
        "chat_application.main.load_users",
        lambda **kwargs: _comp_seed(),
    )
    monkeypatch.setattr(
        "chat_application.auth.users.load_users",
        lambda **kwargs: _comp_seed(),
    )
    monkeypatch.setattr("chat_application.main.settings.zitadel_service_pat", "pat")
    return test_client


def test_list_compliance_users(client: TestClient) -> None:
    response = client.get("/api/compliance-users")
    assert response.status_code == 200
    users = response.json()["users"]
    assert len(users) == 1
    assert users[0]["user_id"] == "comp-001"


def test_list_chat_users_includes_operational(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "chat_application.main.load_users",
        lambda **kwargs: _chat_seed(),
    )
    monkeypatch.setattr(
        "chat_application.auth.users.load_users",
        lambda **kwargs: _chat_seed(),
    )
    response = client.get("/api/chat-users")
    assert response.status_code == 200
    ids = {user["user_id"] for user in response.json()["users"]}
    assert ids == {"comp-001", "pay-101"}


def test_auth_login_success(client: TestClient) -> None:
    session = SessionCredentials(
        session_id="sid",
        session_token="stoken",
        user_id="comp-001",
    )
    with patch("chat_application.main.ZitadelAuthClient") as client_cls:
        client_cls.return_value.login = AsyncMock(return_value=session)
        response = client.post(
            "/api/auth/login",
            json={"user_id": "comp-001", "password": "Password1!"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["session_token"] == "stoken"


def test_auth_login_missing_pat(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
) -> None:
    monkeypatch.setattr("chat_application.main.settings.zitadel_service_pat", None)
    response = test_client.post(
        "/api/auth/login",
        json={"user_id": "comp-001", "password": "Password1!"},
    )
    assert response.status_code == 503


def test_auth_login_failure(client: TestClient) -> None:
    with patch("chat_application.main.ZitadelAuthClient") as client_cls:
        client_cls.return_value.login = AsyncMock(side_effect=RuntimeError("bad password"))
        response = client.post(
            "/api/auth/login",
            json={"user_id": "comp-001", "password": "wrong"},
        )
    assert response.status_code == 401
    assert "login failed" in response.json()["detail"]
