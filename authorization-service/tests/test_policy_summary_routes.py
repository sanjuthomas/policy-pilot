from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from authz.authorization_routes import _opa_client
from authz.dependencies import get_compliance_subject
from authz.main import app
from authz.models import Subject
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    return TestClient(app)


_PAYMENT_SUMMARY = {
    "domain": "payment",
    "actions": {
        "APPROVE": {
            "title": "Funding approval",
            "narrative": (
                "Someone with the FUNDING_APPROVER role, who belongs to the "
                "MIDDLE_OFFICE group and an amount-limit club, and whose "
                "covering_lobs include the instruction's owning LOB, may approve "
                "a payment."
            ),
            "requires": [
                {"kind": "role", "value": "FUNDING_APPROVER"},
                {"kind": "group", "value": "MIDDLE_OFFICE"},
                {"kind": "covering_lobs", "value": "instruction owning LOB"},
            ],
        }
    },
}

_INSTRUCTION_SUMMARY = {
    "domain": "instruction",
    "actions": {
        "APPROVE": {
            "title": "Instruction approval",
            "narrative": (
                "Someone with the INSTRUCTION_APPROVER role whose desk lob "
                "matches the instruction owning LOB may approve."
            ),
            "requires": [
                {"kind": "role", "value": "INSTRUCTION_APPROVER"},
                {"kind": "lob", "value": "subject.lob equals instruction owning LOB"},
            ],
        }
    },
}


def test_policy_summary_requires_auth(client: TestClient) -> None:
    response = client.get(
        "/api/v1/authorization/policy-summary",
        params={"domain": "payment", "action": "APPROVE"},
    )
    assert response.status_code == 403


def test_policy_summary_payment_approve(client: TestClient) -> None:
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    opa = AsyncMock()
    opa.fetch_policy_summary = AsyncMock(return_value=_PAYMENT_SUMMARY)
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_opa_client] = lambda: opa
    try:
        response = client.get(
            "/api/v1/authorization/policy-summary",
            headers={"Authorization": "Bearer comp-token"},
            params={"domain": "payment"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "payment"
    assert body["action"] == "APPROVE"
    assert body["title"] == "Funding approval"
    assert "FUNDING_APPROVER" in body["narrative"]
    assert body["source"] == "opa"
    assert body["requires"][0] == {"kind": "role", "value": "FUNDING_APPROVER"}
    opa.fetch_policy_summary.assert_awaited_once_with("payment")


def test_policy_summary_instruction_approve(client: TestClient) -> None:
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    opa = AsyncMock()
    opa.fetch_policy_summary = AsyncMock(return_value=_INSTRUCTION_SUMMARY)
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_opa_client] = lambda: opa
    try:
        response = client.get(
            "/api/v1/authorization/policy-summary",
            headers={"Authorization": "Bearer comp-token"},
            params={"domain": "instruction", "action": "APPROVE"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "instruction"
    assert body["title"] == "Instruction approval"
    assert any(item["kind"] == "role" for item in body["requires"])


def test_policy_summary_rejects_unknown_domain(client: TestClient) -> None:
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    try:
        response = client.get(
            "/api/v1/authorization/policy-summary",
            headers={"Authorization": "Bearer comp-token"},
            params={"domain": "treasury"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_policy_summary_unknown_action(client: TestClient) -> None:
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    opa = AsyncMock()
    opa.fetch_policy_summary = AsyncMock(return_value=_PAYMENT_SUMMARY)
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_opa_client] = lambda: opa
    try:
        response = client.get(
            "/api/v1/authorization/policy-summary",
            headers={"Authorization": "Bearer comp-token"},
            params={"domain": "payment", "action": "VIEW"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


_AMOUNT_LIMITS = {
    "absolute_limit": 100_000_000_000,
    "club_limits": {
        "UP_TO_100_MILLION_CLUB": 100_000_000,
        "UP_TO_1_BILLION_CLUB": 1_000_000_000,
        "UP_TO_100_BILLION_CLUB": 100_000_000_000,
    },
}


def test_payment_amount_limits_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/authorization/payment-amount-limits")
    assert response.status_code == 403


def test_payment_amount_limits_success(client: TestClient) -> None:
    compliance = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    opa = AsyncMock()
    opa.fetch_payment_amount_limits = AsyncMock(return_value=_AMOUNT_LIMITS)
    app.dependency_overrides[get_compliance_subject] = lambda: compliance
    app.dependency_overrides[_opa_client] = lambda: opa
    try:
        response = client.get(
            "/api/v1/authorization/payment-amount-limits",
            headers={"Authorization": "Bearer comp-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "opa"
    assert body["absolute_limit"] == 100_000_000_000.0
    assert body["club_limits"]["UP_TO_1_BILLION_CLUB"] == 1_000_000_000.0
    opa.fetch_payment_amount_limits.assert_awaited_once()
