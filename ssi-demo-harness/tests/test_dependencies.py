from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from harness.dependencies import get_admin_session, get_subject
from harness.models import Subject


def test_get_subject_requires_bearer() -> None:
    with pytest.raises(HTTPException) as exc:
        get_subject(authorization=None, x_session_id=None)
    assert exc.value.status_code == 401


def test_get_subject_requires_oidc_config() -> None:
    with patch("harness.dependencies.settings.oidc_issuer_url", None):
        with pytest.raises(HTTPException) as exc:
            get_subject(authorization="Bearer token", x_session_id="sess")
    assert exc.value.status_code == 500


def test_get_subject_success() -> None:
    subject = Subject(user_id="admin-001", title="Admin", roles=["PLATFORM_ADMIN"])
    with patch("harness.dependencies.settings.oidc_issuer_url", "http://localhost:8080"), patch(
        "harness.dependencies.subject_from_bearer_token",
        return_value=subject,
    ):
        result = get_subject(authorization="Bearer token-1", x_session_id="sess-1")
    assert result.user_id == "admin-001"


def test_get_admin_session_requires_session_id() -> None:
    with pytest.raises(HTTPException) as exc:
        get_admin_session(authorization="Bearer token", x_session_id=None)
    assert exc.value.status_code == 401


def test_get_admin_session_success() -> None:
    session = get_admin_session(
        authorization="Bearer token-1",
        x_session_id="sess-1",
    )
    assert session.session_id == "sess-1"
    assert session.session_token == "token-1"
