from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ps.dependencies import get_subject
from ps.instruction_client import InstructionNotFoundError
from ps.models.api import Subject
from ps.models.enums import PaymentStatus
from ps.routes import get_service, router
from ps.service import InvalidStateTransitionError, PaymentService


@pytest.fixture
def api_client(subject: Subject, versioned_payment) -> TestClient:
    mock_service = AsyncMock()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_subject] = lambda: subject
    app.dependency_overrides[get_service] = lambda: mock_service
    client = TestClient(app)
    client.mock_service = mock_service  # type: ignore[attr-defined]
    client.versioned_payment = versioned_payment  # type: ignore[attr-defined]
    return client


def _headers() -> dict[str, str]:
    return {
        "X-Subject-User-Id": "alice",
        "X-Subject-Title": "VP Finance",
        "X-Subject-Roles": "PAYMENT_CREATOR",
    }


def test_create_payment_success(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.create.return_value = versioned_payment
    response = api_client.post(
        "/api/v1/payments",
        json={"instruction_id": "instr-001", "value_date": "2026-07-01", "amount": 100.0},
        headers=_headers(),
    )
    assert response.status_code == 201
    assert response.json()["payment_id"] == versioned_payment.payment.payment_id


def test_create_payment_not_found(api_client: TestClient) -> None:
    api_client.mock_service.create.side_effect = InstructionNotFoundError("missing")
    response = api_client.post(
        "/api/v1/payments",
        json={"instruction_id": "missing", "value_date": "2026-07-01", "amount": 100.0},
        headers=_headers(),
    )
    assert response.status_code == 404


def test_create_payment_forbidden(api_client: TestClient) -> None:
    api_client.mock_service.create.side_effect = PermissionError("denied")
    response = api_client.post(
        "/api/v1/payments",
        json={"instruction_id": "instr-001", "value_date": "2026-07-01", "amount": 100.0},
        headers=_headers(),
    )
    assert response.status_code == 403


def test_create_payment_conflict(api_client: TestClient) -> None:
    api_client.mock_service.create.side_effect = ValueError("bad state")
    response = api_client.post(
        "/api/v1/payments",
        json={"instruction_id": "instr-001", "value_date": "2026-07-01", "amount": 100.0},
        headers=_headers(),
    )
    assert response.status_code == 409


def test_create_payment_bad_gateway(api_client: TestClient) -> None:
    api_client.mock_service.create.side_effect = RuntimeError("instruction-service down")
    response = api_client.post(
        "/api/v1/payments",
        json={"instruction_id": "instr-001", "value_date": "2026-07-01", "amount": 100.0},
        headers=_headers(),
    )
    assert response.status_code == 502


def test_update_payment_success(api_client: TestClient, versioned_payment) -> None:
    updated = replace(
        versioned_payment,
        version_number=2,
        payment=versioned_payment.payment.model_copy(update={"amount": 250.0}),
    )
    api_client.mock_service.update.return_value = updated
    response = api_client.put(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}",
        json={
            "instruction_id": versioned_payment.payment.instruction_id,
            "value_date": "2026-07-02",
            "amount": 250.0,
        },
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["amount"] == 250.0
    assert response.json()["version_number"] == 2


def test_update_payment_forbidden(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.update.side_effect = PermissionError("denied")
    response = api_client.put(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}",
        json={
            "instruction_id": versioned_payment.payment.instruction_id,
            "value_date": "2026-07-02",
            "amount": 250.0,
        },
        headers=_headers(),
    )
    assert response.status_code == 403


def test_update_payment_invalid_state(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.update.side_effect = InvalidStateTransitionError("only DRAFT")
    response = api_client.put(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}",
        json={
            "instruction_id": versioned_payment.payment.instruction_id,
            "value_date": "2026-07-02",
            "amount": 250.0,
        },
        headers=_headers(),
    )
    assert response.status_code == 409


def test_update_payment_not_found(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.update.side_effect = LookupError("missing")
    response = api_client.put(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}",
        json={
            "instruction_id": versioned_payment.payment.instruction_id,
            "value_date": "2026-07-02",
            "amount": 250.0,
        },
        headers=_headers(),
    )
    assert response.status_code == 404


def test_list_payments(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.list.return_value = [versioned_payment]
    response = api_client.get("/api/v1/payments", headers=_headers())
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_payment_forbidden(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.get.side_effect = PermissionError("denied")
    response = api_client.get(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}",
        headers=_headers(),
    )
    assert response.status_code == 403


def test_get_payment(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.get.return_value = versioned_payment
    response = api_client.get(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}",
        headers=_headers(),
    )
    assert response.status_code == 200


def test_list_payment_versions(api_client: TestClient, versioned_payment) -> None:
    api_client.mock_service.list_versions.return_value = [versioned_payment]
    response = api_client.get(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}/versions",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    api_client.mock_service.list_versions.assert_awaited_once()


def test_list_payment_versions_not_found(api_client: TestClient) -> None:
    api_client.mock_service.list_versions.side_effect = LookupError("missing")
    response = api_client.get("/api/v1/payments/missing/versions", headers=_headers())
    assert response.status_code == 404


def test_get_payment_not_found(api_client: TestClient) -> None:
    api_client.mock_service.get.side_effect = LookupError("missing")
    response = api_client.get("/api/v1/payments/missing", headers=_headers())
    assert response.status_code == 404


def test_submit_payment(api_client: TestClient, versioned_payment) -> None:
    submitted = replace(
        versioned_payment,
        payment=versioned_payment.payment.model_copy(
            update={"status": PaymentStatus.SUBMITTED}
        ),
    )
    api_client.mock_service.submit.return_value = submitted
    response = api_client.post(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}/submit",
        headers={**_headers(), "Authorization": "Bearer user-token"},
    )
    assert response.status_code == 200


def test_approve_payment(api_client: TestClient, versioned_payment) -> None:
    approved = replace(
        versioned_payment,
        payment=versioned_payment.payment.model_copy(
            update={"status": PaymentStatus.APPROVED}
        ),
    )
    api_client.mock_service.approve.return_value = approved
    response = api_client.post(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}/approve",
        headers=_headers(),
    )
    assert response.status_code == 200


def test_reject_payment(api_client: TestClient, versioned_payment) -> None:
    rejected = replace(
        versioned_payment,
        payment=versioned_payment.payment.model_copy(
            update={"status": PaymentStatus.REJECTED}
        ),
    )
    api_client.mock_service.reject.return_value = rejected
    response = api_client.post(
        f"/api/v1/payments/{versioned_payment.payment.payment_id}/reject",
        json={"reason": "docs missing"},
        headers=_headers(),
    )
    assert response.status_code == 200


def test_submit_payment_errors(api_client: TestClient, versioned_payment) -> None:
    payment_id = versioned_payment.payment.payment_id
    api_client.mock_service.submit.side_effect = LookupError("missing")
    response = api_client.post(
        f"/api/v1/payments/{payment_id}/submit",
        headers=_headers(),
    )
    assert response.status_code == 404

    api_client.mock_service.submit.side_effect = PermissionError("denied")
    response = api_client.post(
        f"/api/v1/payments/{payment_id}/submit",
        headers=_headers(),
    )
    assert response.status_code == 403

    api_client.mock_service.submit.side_effect = InvalidStateTransitionError("bad state")
    response = api_client.post(
        f"/api/v1/payments/{payment_id}/submit",
        headers=_headers(),
    )
    assert response.status_code == 409


def test_approve_payment_errors(api_client: TestClient, versioned_payment) -> None:
    payment_id = versioned_payment.payment.payment_id
    api_client.mock_service.approve.side_effect = LookupError("missing")
    response = api_client.post(
        f"/api/v1/payments/{payment_id}/approve",
        headers=_headers(),
    )
    assert response.status_code == 404

    api_client.mock_service.approve.side_effect = PermissionError("denied")
    response = api_client.post(
        f"/api/v1/payments/{payment_id}/approve",
        headers=_headers(),
    )
    assert response.status_code == 403


def test_reject_payment_errors(api_client: TestClient, versioned_payment) -> None:
    payment_id = versioned_payment.payment.payment_id
    api_client.mock_service.reject.side_effect = PermissionError("denied")
    response = api_client.post(
        f"/api/v1/payments/{payment_id}/reject",
        json={"reason": "n/a"},
        headers=_headers(),
    )
    assert response.status_code == 403


def test_get_service_returns_payment_service() -> None:
    from ps.routes import get_service

    assert isinstance(get_service(), PaymentService)
