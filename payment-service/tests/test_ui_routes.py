from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ps.admin import get_admin_subject
from ps.models.api import Subject
from ps.ui_routes import router


@pytest.fixture
def ui_client(payment) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    admin = Subject(user_id="admin-001", title="Admin", roles=["PLATFORM_ADMIN"])
    app.dependency_overrides[get_admin_subject] = lambda: admin
    client = TestClient(app)
    client.payment = payment  # type: ignore[attr-defined]
    return client


@patch("ps.ui_routes.PaymentRepository")
def test_ui_list_payments_instruction_filter(
    mock_repo_cls: AsyncMock, ui_client: TestClient, versioned_payment
) -> None:
    mock_repo = AsyncMock()
    mock_repo.list_current.return_value = [versioned_payment]
    mock_repo_cls.return_value = mock_repo

    instruction_id = "3bcb9b9a-9415-44ce-b707-4cc4c8281bb9"
    response = ui_client.get(
        "/api/ui/payments",
        params={"instruction_id": instruction_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["payments"][0]["instruction_id"] == ui_client.payment.instruction_id
    mock_repo.list_current.assert_awaited_once_with(
        status=None,
        instruction_id=instruction_id,
        limit=200,
    )


@patch("ps.ui_routes.PaymentRepository")
def test_ui_list_payments_owning_lob_filter(
    mock_repo_cls: AsyncMock, ui_client: TestClient, versioned_payment
) -> None:
    other = versioned_payment.payment.model_copy(update={"owning_lob": "FX"})
    other_record = replace(versioned_payment, payment=other)
    mock_repo = AsyncMock()
    mock_repo.list_current.return_value = [versioned_payment, other_record]
    mock_repo_cls.return_value = mock_repo

    response = ui_client.get("/api/ui/payments", params={"owning_lob": "CORP"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["payments"][0]["owning_lob"] == "CORP"


@patch("ps.ui_routes.PaymentRepository")
def test_ui_get_payment_success(
    mock_repo_cls: AsyncMock, ui_client: TestClient, versioned_payment
) -> None:
    mock_repo = AsyncMock()
    mock_repo.get_current.return_value = versioned_payment
    mock_repo_cls.return_value = mock_repo

    payment_id = versioned_payment.payment.payment_id
    response = ui_client.get(f"/api/ui/payments/{payment_id}")

    assert response.status_code == 200
    assert response.json()["payment"]["payment_id"] == payment_id


@patch("ps.ui_routes.PaymentRepository")
def test_ui_get_payment_not_found(mock_repo_cls: AsyncMock, ui_client: TestClient) -> None:
    from ps.repository import PaymentNotFoundError

    mock_repo = AsyncMock()
    mock_repo.get_current.side_effect = PaymentNotFoundError("missing")
    mock_repo_cls.return_value = mock_repo

    response = ui_client.get("/api/ui/payments/missing")
    assert response.status_code == 404


def test_ui_static_pages(ui_client: TestClient, versioned_payment) -> None:
    payment_id = versioned_payment.payment.payment_id
    assert ui_client.get("/ui").status_code == 200
    assert ui_client.get(f"/ui/payments/{payment_id}").status_code == 200
