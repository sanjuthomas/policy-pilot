from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ps.admin import get_admin_subject
from ps.auth_routes import router as auth_router
from ps.models.api import Subject


@pytest.fixture
def admin_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    admin = Subject(user_id="admin-001", title="Admin", roles=["PLATFORM_ADMIN"])
    app.dependency_overrides[get_admin_subject] = lambda: admin
    return TestClient(app)


def test_get_admin_subject_requires_platform_admin() -> None:
    subject = Subject(user_id="u1", title="User", roles=["PAYMENT_CREATOR"])
    with pytest.raises(Exception) as exc:
        get_admin_subject(subject)
    assert exc.value.status_code == 403


def test_get_admin_subject_allows_platform_admin() -> None:
    subject = Subject(user_id="admin-001", title="Admin", roles=["PLATFORM_ADMIN"])
    assert get_admin_subject(subject).user_id == "admin-001"


def test_admin_login_not_configured() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    with patch("ps.auth_routes.settings.zitadel_service_pat", None):
        response = client.post(
            "/api/auth/login",
            json={"user_id": "admin-001", "password": "Password1!"},
        )
    assert response.status_code == 503


def test_admin_login_success() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    session = MagicMock(
        user_id="admin-001",
        session_id="sess-1",
        session_token="token-1",
    )
    with patch("ps.auth_routes.settings.zitadel_service_pat", "pat"), patch(
        "ps.auth_routes.settings.oidc_issuer_url",
        "http://localhost:8080",
    ), patch("ps.auth_routes.ZitadelLoginClient") as mock_client:
        mock_client.return_value.login.return_value = session
        response = client.post(
            "/api/auth/login",
            json={"user_id": "admin-001", "password": "Password1!"},
        )
    assert response.status_code == 200
    assert response.json()["session_token"] == "token-1"
