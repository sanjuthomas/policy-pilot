from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from audit_console.auth import AuditorSubject, resolve_auditor
from audit_console.routes import repository, router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[resolve_auditor] = lambda: AuditorSubject(
        user_id="audit-001",
        title="Technology Auditor",
        roles=["TECH_AUDITOR"],
        groups=["TECH_AUDITORS"],
    )
    return TestClient(app)


def test_static_pages() -> None:
    test_client = client()
    assert test_client.get("/").status_code == 200
    assert test_client.get("/events/payment/E-1").status_code == 200
    assert test_client.get("/audit/AUD-1").status_code == 200


def test_event_routes() -> None:
    with (
        patch.object(
            repository,
            "list_events",
            AsyncMock(return_value=[{"event_id": "E-1", "domain": "payment"}]),
        ),
        patch.object(
            repository,
            "get_event",
            AsyncMock(return_value={"event_id": "E-1", "domain": "payment"}),
        ),
    ):
        test_client = client()
        listed = test_client.get("/api/security-events?source=payment")
        detail = test_client.get("/api/security-events/payment/E-1")
    assert listed.json()["count"] == 1
    assert detail.json()["event"]["event_id"] == "E-1"


def test_audit_routes() -> None:
    with (
        patch.object(
            repository,
            "list_executions",
            AsyncMock(return_value=[{"execution_id": "AUD-1"}]),
        ),
        patch.object(
            repository,
            "get_execution",
            AsyncMock(return_value={"execution_id": "AUD-1"}),
        ),
        patch.object(
            repository,
            "get_opa_evidence",
            AsyncMock(return_value={"source": "security_event"}),
        ),
    ):
        test_client = client()
        listed = test_client.get("/api/audit-executions")
        detail = test_client.get("/api/audit-executions/AUD-1")
        opa = test_client.get("/api/audit-executions/AUD-1/opa")
    assert listed.json()["count"] == 1
    assert detail.json()["execution"]["execution_id"] == "AUD-1"
    assert opa.json()["source"] == "security_event"
