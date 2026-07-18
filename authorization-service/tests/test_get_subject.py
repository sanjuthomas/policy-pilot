from unittest.mock import patch

import pytest
from authz.dependencies import get_subject, require_obo_subject
from authz.models import Subject
from fastapi import HTTPException


def test_require_obo_rejects_missing_obo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    with pytest.raises(HTTPException) as exc:
        require_obo_subject(
            authorization="Bearer svc-token",
            x_session_id="sess",
            x_on_behalf_of=None,
            x_on_behalf_of_session_id=None,
        )
    assert exc.value.status_code == 403
    assert "X-On-Behalf-Of" in str(exc.value.detail)


def test_get_subject_requires_obo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    with pytest.raises(HTTPException) as exc:
        get_subject(
            authorization="Bearer token",
            x_session_id="sess",
            x_on_behalf_of=None,
            x_on_behalf_of_session_id=None,
        )
    assert exc.value.status_code == 403


def test_get_subject_obo_uses_user_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    service = Subject(user_id="svc-chat", title="Service", roles=["INSTRUCTION_VIEWER"])
    user = Subject(
        user_id="comp-001",
        title="Analyst",
        roles=["COMPLIANCE_ANALYST"],
        delegated_by="svc-chat",
        delegated_by_roles=["INSTRUCTION_VIEWER"],
    )
    with (
        patch("authz.dependencies.subject_from_bearer_token", return_value=service),
        patch("authz.dependencies.subject_from_obo_call", return_value=user) as obo,
    ):
        result = get_subject(
            authorization="Bearer svc-token",
            x_session_id="svc-sess",
            x_on_behalf_of="user-token",
            x_on_behalf_of_session_id="user-sess",
        )
    assert result.user_id == "comp-001"
    assert result.delegated_by == "svc-chat"
    obo.assert_called_once_with(
        "svc-token",
        "user-token",
        service_session_id="svc-sess",
        user_session_id="user-sess",
    )
