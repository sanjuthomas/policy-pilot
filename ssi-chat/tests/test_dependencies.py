from __future__ import annotations

from unittest.mock import patch

import pytest
from chat_application.auth.subject import Subject
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import chat_application.main as main_module
    from chat_application.auth.dependencies import get_chat_subject

    monkeypatch.setattr("chat_application.config.settings.oidc_issuer_url", "http://localhost:8080")
    main_module.app.dependency_overrides.pop(get_chat_subject, None)
    return test_client


def test_get_chat_subject_rejects_missing_bearer(auth_client: TestClient) -> None:
    response = auth_client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 401


def test_get_chat_subject_rejects_unrelated_role(auth_client: TestClient) -> None:
    subject = Subject(user_id="fo-001", title="Trader", roles=["INSTRUCTION_CREATOR"])
    with patch("chat_application.auth.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 403


def test_get_chat_subject_allows_compliance_analyst(auth_client: TestClient) -> None:
    import chat_application.main as main_module

    subject = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    main_module.rag_service = None
    with patch("chat_application.auth.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 503


def test_get_chat_subject_allows_payment_creator(auth_client: TestClient) -> None:
    import chat_application.main as main_module

    subject = Subject(
        user_id="pay-101",
        title="Payment Ops",
        roles=["PAYMENT_CREATOR"],
        groups=["MIDDLE_OFFICE"],
        covering_lobs=["FICC"],
    )
    main_module.rag_service = None
    with patch("chat_application.auth.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 503


def test_get_chat_subject_allows_funding_approver(auth_client: TestClient) -> None:
    import chat_application.main as main_module

    subject = Subject(
        user_id="pay-201",
        title="VP",
        roles=["FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"],
        covering_lobs=["FICC", "FX"],
    )
    main_module.rag_service = None
    with patch("chat_application.auth.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 503


def test_get_chat_subject_allows_platform_admin(auth_client: TestClient) -> None:
    import chat_application.main as main_module

    subject = Subject(
        user_id="admin-001",
        title="Platform Administrator",
        roles=["PLATFORM_ADMIN"],
    )
    main_module.rag_service = None
    with patch("chat_application.auth.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 503
