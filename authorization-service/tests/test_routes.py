from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from authz.ilm_client import InstructionNotFoundError
from authz.models import Subject
from authz.payment_repository import PaymentNotFoundError


@pytest.fixture
def compliance_subject() -> Subject:
    return Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )


def test_health(test_client: TestClient) -> None:
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_eligible_approvers_requires_auth(test_client: TestClient) -> None:
    response = test_client.post("/api/v1/payments/p1/eligible-approvers")
    assert response.status_code == 401


def test_eligible_approvers_success(
    test_client: TestClient,
    compliance_subject: Subject,
) -> None:
    from authz import main as main_module
    from authz.models import EligibleApprover, PaymentEligibleApproversResponse

    main_module.eligibility_service = AsyncMock()
    main_module.eligibility_service.eligible_approvers_for_payment.return_value = (
        PaymentEligibleApproversResponse(
            payment_id="p1",
            instruction_id="i1",
            payment_status="SUBMITTED",
            amount=1_000_000,
            currency="USD",
            owning_lob="FICC",
            instruction_status="STANDING",
            evaluated_at="2026-06-27T00:00:00+00:00",
            eligible=[
                EligibleApprover(
                    user_id="pay-201",
                    display_name="Laurent, Sophie (pay-201)",
                    title="VP",
                    allow_basis=["has_role"],
                )
            ],
            candidates_evaluated=2,
        )
    )

    with patch("authz.dependencies.subject_from_bearer_token", return_value=compliance_subject):
        response = test_client.post(
            "/api/v1/payments/p1/eligible-approvers",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json()["payment_id"] == "p1"


def test_eligible_approvers_forbidden_for_non_compliance(test_client: TestClient) -> None:
    subject = Subject(user_id="pay-201", title="VP", roles=["FUNDING_APPROVER"])
    with patch("authz.dependencies.subject_from_bearer_token", return_value=subject):
        response = test_client.post(
            "/api/v1/payments/p1/eligible-approvers",
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 403


def test_eligible_approvers_payment_not_found(
    test_client: TestClient,
    compliance_subject: Subject,
) -> None:
    from authz import main as main_module

    main_module.eligibility_service = AsyncMock()
    main_module.eligibility_service.eligible_approvers_for_payment.side_effect = (
        PaymentNotFoundError("missing")
    )

    with patch("authz.dependencies.subject_from_bearer_token", return_value=compliance_subject):
        response = test_client.post(
            "/api/v1/payments/missing/eligible-approvers",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 404


def test_eligible_approvers_instruction_not_found(
    test_client: TestClient,
    compliance_subject: Subject,
) -> None:
    from authz import main as main_module

    main_module.eligibility_service = AsyncMock()
    main_module.eligibility_service.eligible_approvers_for_payment.side_effect = (
        InstructionNotFoundError("missing instruction")
    )

    with patch("authz.dependencies.subject_from_bearer_token", return_value=compliance_subject):
        response = test_client.post(
            "/api/v1/payments/p1/eligible-approvers",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 404


def test_instruction_eligible_approvers_success(
    test_client: TestClient,
    compliance_subject: Subject,
) -> None:
    from authz import main as main_module
    from authz.models import EligibleApprover, InstructionEligibleApproversResponse

    main_module.eligibility_service = AsyncMock()
    main_module.eligibility_service.eligible_approvers_for_instruction.return_value = (
        InstructionEligibleApproversResponse(
            instruction_id="i1",
            instruction_status="PENDING",
            instruction_type="STANDING",
            owning_lob="FICC",
            created_by_user_id="ficc-101",
            created_by_title="Analyst",
            evaluated_at="2026-06-27T00:00:00+00:00",
            eligible=[
                EligibleApprover(
                    user_id="ficc-300",
                    display_name="Vasquez, Elena (ficc-300)",
                    title="Vice President",
                    allow_basis=["approval matrix"],
                )
            ],
            candidates_evaluated=4,
        )
    )

    with patch("authz.dependencies.subject_from_bearer_token", return_value=compliance_subject):
        response = test_client.post(
            "/api/v1/instructions/i1/eligible-approvers",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json()["instruction_id"] == "i1"
