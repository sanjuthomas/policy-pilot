from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from harness.admin import get_admin_subject
from harness.app import app
from harness.dependencies import get_admin_session
from harness.models import Subject
from harness.zitadel_auth import SessionCredentials


def _admin_client() -> TestClient:
    admin = Subject(user_id="admin-001", title="Admin", roles=["PLATFORM_ADMIN"])
    session = SessionCredentials(session_id="sess-1", session_token="token-1")
    app.dependency_overrides[get_admin_subject] = lambda: admin
    app.dependency_overrides[get_admin_session] = lambda: session
    return TestClient(app)


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_status_requires_admin() -> None:
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 401


def test_status_with_admin() -> None:
    client = _admin_client()
    with patch("harness.app._fetch_api_instructions", return_value=[]), patch(
        "harness.app._fetch_api_payments",
        return_value=[],
    ), patch("harness.app._count_security_events", return_value=0), patch(
        "harness.app._count_payment_security_events",
        return_value=0,
    ):
        response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["instruction_total"] == 0
    assert body["security_event_count"] == 0
    app.dependency_overrides.clear()


def test_action_requires_admin() -> None:
    client = TestClient(app)
    response = client.post("/api/actions/create-instructions", json={"count": 1})
    assert response.status_code == 401


def test_suspend_action_requires_admin() -> None:
    client = TestClient(app)
    response = client.post("/api/actions/suspend-instructions", json={"count": 1})
    assert response.status_code == 401
