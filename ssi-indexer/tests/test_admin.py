from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from etl.admin import get_admin_subject
from etl.auth_routes import router as auth_router
from etl.models import Subject
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_get_admin_subject_requires_platform_admin() -> None:
    subject = Subject(user_id="u1", title="User", roles=["PAYMENT_CREATOR"])
    with pytest.raises(Exception) as exc:
        get_admin_subject(subject)
    assert exc.value.status_code == 403


def test_admin_login_missing_pat() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    with patch("etl.auth_routes.settings.zitadel_service_pat", None):
        response = client.post(
            "/api/auth/login",
            json={"user_id": "admin-001", "password": "Password1!"},
        )
    assert response.status_code == 503


def test_admin_login_failure_maps_404_detail() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    with patch("etl.auth_routes.settings.zitadel_service_pat", "pat"), patch(
        "etl.auth_routes.settings.oidc_issuer_url",
        "http://localhost:8080",
    ), patch("etl.auth_routes.ZitadelLoginClient") as mock_client:
        mock_client.return_value.login.side_effect = RuntimeError("404 sessions missing")
        response = client.post(
            "/api/auth/login",
            json={"user_id": "admin-001", "password": "bad"},
        )
    assert response.status_code == 401
    assert "session API returned 404" in response.json()["detail"]


def test_zitadel_base_not_configured() -> None:
    from etl.auth_routes import _zitadel_base

    with patch("etl.auth_routes.settings") as mock_settings:
        mock_settings.zitadel_internal_url = None
        mock_settings.oidc_internal_url = None
        mock_settings.oidc_issuer_url = None
        with pytest.raises(Exception) as exc:
            _zitadel_base()
    assert exc.value.status_code == 503


def test_admin_login_success() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)
    session = MagicMock(
        user_id="admin-001",
        session_id="sess-1",
        session_token="token-1",
    )
    with patch("etl.auth_routes.settings.zitadel_service_pat", "pat"), patch(
        "etl.auth_routes.settings.oidc_issuer_url",
        "http://localhost:8080",
    ), patch("etl.auth_routes.ZitadelLoginClient") as mock_client:
        mock_client.return_value.login.return_value = session
        response = client.post(
            "/api/auth/login",
            json={"user_id": "admin-001", "password": "Password1!"},
        )
    assert response.status_code == 200
