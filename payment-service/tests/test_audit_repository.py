from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from ps.audit_repository import serialize_audit_execution
from ps.audit_routes import get_audit_repo, router
from ps.dependencies import get_subject
from ps.models.api import Subject
from ps.models.audit import CreateAuditExecutionRequest, PatchAuditExecutionRequest


def test_serialize_audit_execution_normalizes_ids_and_timestamps() -> None:
    doc = {
        "_id": "AUD-1",
        "created_at": datetime(2026, 7, 24, 12, 0, 0),
        "timeline": [{"at": datetime(2026, 7, 24, 12, 0, 1), "step": "identity", "summary": "ok"}],
    }
    out = serialize_audit_execution(doc)
    assert out["execution_id"] == "AUD-1"
    assert out["created_at"].endswith("Z")
    assert out["timeline"][0]["at"].endswith("Z")


def test_audit_routes_create_and_patch() -> None:
    app = FastAPI()
    app.include_router(router)
    subject = Subject(
        user_id="alice",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
    )
    repo = AsyncMock()
    repo.create = AsyncMock(
        return_value={
            "execution_id": "AUD-1",
            "capability": "CREATE_PAYMENT",
            "status": "AWAITING_CONFIRMATION",
            "actor": {"user_id": "alice"},
        }
    )
    repo.get = AsyncMock(
        return_value={
            "execution_id": "AUD-1",
            "actor": {"user_id": "alice"},
            "status": "AWAITING_CONFIRMATION",
        }
    )
    repo.patch = AsyncMock(
        return_value={
            "execution_id": "AUD-1",
            "status": "CANCELLED",
            "actor": {"user_id": "alice"},
        }
    )
    app.dependency_overrides[get_subject] = lambda: subject
    app.dependency_overrides[get_audit_repo] = lambda: repo

    client = TestClient(app)
    create_body = CreateAuditExecutionRequest(
        status="AWAITING_CONFIRMATION",
        outcome="allow",
        request={"instruction_id": "I-1", "amount": 1000},
    )
    created = client.post("/audit-executions", json=create_body.model_dump())
    assert created.status_code == 201
    assert created.json()["execution_id"] == "AUD-1"

    patched = client.patch(
        "/audit-executions/AUD-1",
        json=PatchAuditExecutionRequest(status="CANCELLED", outcome="cancelled").model_dump(
            exclude_none=True
        ),
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "CANCELLED"
