from authz.config import settings
from authz.dependencies import get_compliance_subject
from authz.models import Subject
from fastapi import HTTPException
import pytest


def test_compliance_role_set_includes_analyst() -> None:
    assert "COMPLIANCE_ANALYST" in settings.compliance_role_set


def test_compliance_role_set_includes_platform_admin() -> None:
    assert "PLATFORM_ADMIN" in settings.compliance_role_set


def test_get_compliance_subject_rejects_non_compliance() -> None:
    subject = Subject(
        user_id="pay-201",
        title="VP",
        roles=["FUNDING_APPROVER"],
    )
    with pytest.raises(HTTPException) as exc:
        get_compliance_subject(subject)
    assert exc.value.status_code == 403


def test_get_compliance_subject_allows_analyst() -> None:
    subject = Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )
    assert get_compliance_subject(subject).user_id == "comp-001"


def test_get_compliance_subject_allows_platform_admin() -> None:
    subject = Subject(
        user_id="admin-001",
        title="Platform Administrator",
        roles=["PLATFORM_ADMIN"],
    )
    assert get_compliance_subject(subject).user_id == "admin-001"
