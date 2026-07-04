from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from chat_application.zitadel_auth import SessionCredentials
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test_client: TestClient) -> TestClient:
    users_file = tmp_path / "users.yaml"
    users_file.write_text(
        """
users:
  - user_id: comp-001
    given_name: Alex
    family_name: Morgan
    title: Compliance Analyst
    roles: [COMPLIANCE_ANALYST]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("chat_application.main.settings.users_file", users_file)
    monkeypatch.setattr("chat_application.main.settings.zitadel_service_pat", "pat")
    return test_client


def test_list_compliance_users(client: TestClient) -> None:
    response = client.get("/api/compliance-users")
    assert response.status_code == 200
    users = response.json()["users"]
    assert len(users) == 1
    assert users[0]["user_id"] == "comp-001"


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
