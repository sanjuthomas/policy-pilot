from unittest.mock import patch

import pytest
from authz.dependencies import get_subject
from authz.models import Subject
from fastapi import HTTPException


def test_get_subject_requires_bearer() -> None:
    with pytest.raises(HTTPException) as exc:
        get_subject(authorization=None, x_session_id=None)
    assert exc.value.status_code == 401


def test_get_subject_parses_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("authz.config.settings.oidc_issuer_url", "http://localhost:8080")
    subject = Subject(user_id="comp-001", title="Analyst", roles=["COMPLIANCE_ANALYST"])
    with patch("authz.dependencies.subject_from_bearer_token", return_value=subject):
        result = get_subject(authorization="Bearer token", x_session_id="sess")
    assert result.user_id == "comp-001"
