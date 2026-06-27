from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from chat_application.subject import Subject


@pytest.fixture
def auth_client(test_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import chat_application.main as main_module
    from chat_application.dependencies import get_compliance_subject

    monkeypatch.setattr("chat_application.config.settings.oidc_issuer_url", "http://localhost:8080")
    main_module.app.dependency_overrides.pop(get_compliance_subject, None)
    return test_client


def test_get_compliance_subject_rejects_missing_bearer(auth_client: TestClient) -> None:
    response = auth_client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 401


def test_get_compliance_subject_rejects_non_compliance_role(auth_client: TestClient) -> None:
    subject = Subject(user_id="pay-201", title="VP", roles=["FUNDING_APPROVER"])
    with patch("chat_application.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 403


def test_get_compliance_subject_allows_compliance_analyst(auth_client: TestClient) -> None:
    import chat_application.main as main_module

    subject = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    main_module.rag_service = None
    with patch("chat_application.dependencies.subject_from_bearer_token", return_value=subject):
        response = auth_client.post(
            "/api/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "hello"},
        )
    assert response.status_code == 503
