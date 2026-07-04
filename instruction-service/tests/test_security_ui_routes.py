from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from inst.admin import get_admin_subject
from inst.models.api import Subject
from inst.security_ui_routes import router, security_event_ui_store


def test_security_ui_list_and_get_event() -> None:
    app = FastAPI()
    app.include_router(router)
    admin = Subject(user_id="admin", title="Admin", roles=["PLATFORM_ADMIN"])
    app.dependency_overrides[get_admin_subject] = lambda: admin

    with patch.object(
        security_event_ui_store,
        "list_recent",
        AsyncMock(return_value=[{"event_id": "e1", "severity": "INFO"}]),
    ), patch.object(
        security_event_ui_store,
        "get_by_event_id",
        AsyncMock(return_value={"event_id": "e1", "severity": "INFO"}),
    ):
        client = TestClient(app)
        list_response = client.get("/api/ui/security-events")
        assert list_response.status_code == 200
        assert list_response.json()["count"] == 1

        get_response = client.get("/api/ui/security-events/e1")
        assert get_response.status_code == 200
        assert get_response.json()["event"]["event_id"] == "e1"


def test_security_ui_get_event_not_found() -> None:
    app = FastAPI()
    app.include_router(router)
    admin = Subject(user_id="admin", title="Admin", roles=["PLATFORM_ADMIN"])
    app.dependency_overrides[get_admin_subject] = lambda: admin

    with patch.object(security_event_ui_store, "get_by_event_id", AsyncMock(return_value=None)):
        client = TestClient(app)
        response = client.get("/api/ui/security-events/missing")
        assert response.status_code == 404


def test_security_ui_static_pages() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/ui/security-events").status_code == 200
    assert client.get("/ui/security-events/events/e1").status_code == 200
