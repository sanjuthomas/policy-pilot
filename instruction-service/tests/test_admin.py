import pytest
from inst.admin import get_admin_subject
from inst.dependencies import get_compliance_subject
from inst.models.api import Subject


def test_get_compliance_subject_allows_platform_admin(sample_subject: Subject) -> None:
    admin = sample_subject.model_copy(update={"roles": ["PLATFORM_ADMIN"]})
    assert get_compliance_subject(admin) is admin


def test_get_compliance_subject_allows_compliance_role(sample_subject: Subject) -> None:
    analyst = sample_subject.model_copy(update={"roles": ["COMPLIANCE_ANALYST"]})
    assert get_compliance_subject(analyst) is analyst


def test_get_compliance_subject_allows_other_roles(sample_subject: Subject) -> None:
    assert get_compliance_subject(sample_subject) is sample_subject


def test_get_admin_subject_uses_direct_jwt(
    sample_subject: Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import patch

    monkeypatch.setattr("inst.admin.settings.oidc_issuer_url", "http://localhost:8080")
    admin = sample_subject.model_copy(update={"roles": ["PLATFORM_ADMIN"]})
    with patch("inst.admin.subject_from_bearer_token", return_value=admin):
        assert (
            get_admin_subject(authorization="Bearer token", x_session_id="sess") is admin
        )
