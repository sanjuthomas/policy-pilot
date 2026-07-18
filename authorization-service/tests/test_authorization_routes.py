from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from authz.authorization_routes import _eligibility_service, _user_directory
from authz.dependencies import require_obo_subject
from authz.main import app
from authz.models import PaymentEligibilityContext, Subject
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    return TestClient(app)


def test_evaluate_instruction_requires_service_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/authorization/instructions/evaluate",
        json={
            "action": "CREATE",
            "instruction": {"status": "DRAFT", "type": "STANDING", "owning_lob": "FICC"},
            "account": {"lob": "FICC"},
        },
    )
    assert response.status_code == 401


def test_payment_eligible_approvers_requires_obo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/authorization/payments/eligible-approvers",
        headers={"Authorization": "Bearer svc-token"},
        json={
            "payment": {
                "payment_id": "p1",
                "instruction_id": "i1",
                "instruction_version": 1,
                "status": "SUBMITTED",
                "amount": 100.0,
                "currency": "USD",
                "owning_lob": "FICC",
                "created_by_user_id": "pay-101",
            },
            "instruction_status": "APPROVED",
        },
    )
    assert response.status_code == 403
    assert "X-On-Behalf-Of" in response.json()["detail"]


def test_payment_eligible_approvers_success(client: TestClient) -> None:
    obo_subject = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
        delegated_by="svc-payment",
    )
    response_payload = {
        "payment_id": "p1",
        "instruction_id": "i1",
        "payment_status": "SUBMITTED",
        "amount": 100.0,
        "currency": "USD",
        "owning_lob": "FICC",
        "instruction_status": "APPROVED",
        "evaluated_at": "2026-01-01T00:00:00Z",
        "eligible": [],
        "candidates_evaluated": 0,
    }

    mock_service = AsyncMock()
    mock_service.eligible_approvers_for_payment.return_value = response_payload

    app.dependency_overrides[require_obo_subject] = lambda: obo_subject
    app.dependency_overrides[_eligibility_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/authorization/payments/eligible-approvers",
            headers={
                "Authorization": "Bearer svc-token",
                "X-On-Behalf-Of": "user-token",
            },
            json={
                "payment": PaymentEligibilityContext(
                    payment_id="p1",
                    instruction_id="i1",
                    instruction_version=1,
                    status="SUBMITTED",
                    amount=100.0,
                    currency="USD",
                    owning_lob="FICC",
                    created_by_user_id="pay-101",
                ).model_dump(mode="json"),
                "instruction_status": "APPROVED",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["payment_id"] == "p1"


def test_payment_eligible_submitters_requires_obo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/authorization/payments/eligible-submitters",
        headers={"Authorization": "Bearer svc-token"},
        json={
            "payment": {
                "payment_id": "p1",
                "instruction_id": "i1",
                "instruction_version": 1,
                "status": "DRAFT",
                "amount": 100.0,
                "currency": "USD",
                "owning_lob": "FICC",
                "created_by_user_id": "pay-101",
            },
            "instruction_status": "APPROVED",
        },
    )
    assert response.status_code == 403
    assert "X-On-Behalf-Of" in response.json()["detail"]


def test_payment_eligible_submitters_success(client: TestClient) -> None:
    obo_subject = Subject(
        user_id="pay-101",
        title="Analyst",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        delegated_by="svc-chat",
    )
    response_payload = {
        "payment_id": "p1",
        "instruction_id": "i1",
        "payment_status": "DRAFT",
        "amount": 100.0,
        "currency": "USD",
        "owning_lob": "FICC",
        "instruction_status": "APPROVED",
        "evaluated_at": "2026-01-01T00:00:00Z",
        "eligible": [],
        "candidates_evaluated": 0,
        "submit_blocked_reason": None,
    }

    mock_service = AsyncMock()
    mock_service.eligible_submitters_for_payment.return_value = response_payload

    app.dependency_overrides[require_obo_subject] = lambda: obo_subject
    app.dependency_overrides[_eligibility_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/authorization/payments/eligible-submitters",
            headers={
                "Authorization": "Bearer svc-token",
                "X-On-Behalf-Of": "user-token",
            },
            json={
                "payment": PaymentEligibilityContext(
                    payment_id="p1",
                    instruction_id="i1",
                    instruction_version=1,
                    status="DRAFT",
                    amount=100.0,
                    currency="USD",
                    owning_lob="FICC",
                    created_by_user_id="pay-101",
                ).model_dump(mode="json"),
                "instruction_status": "APPROVED",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["payment_id"] == "p1"
    mock_service.eligible_submitters_for_payment.assert_awaited_once()
