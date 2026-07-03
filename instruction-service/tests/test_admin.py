import pytest
from fastapi import HTTPException

from inst.admin import get_admin_subject
from inst.dependencies import get_compliance_subject
from inst.models.api import Subject


def test_get_compliance_subject_allows_platform_admin(sample_subject: Subject) -> None:
    admin = sample_subject.model_copy(update={"roles": ["PLATFORM_ADMIN"]})
    assert get_compliance_subject(admin) is admin


def test_get_compliance_subject_allows_compliance_role(sample_subject: Subject) -> None:
    analyst = sample_subject.model_copy(update={"roles": ["COMPLIANCE_ANALYST"]})
    assert get_compliance_subject(analyst) is analyst


def test_get_compliance_subject_denies_other_roles(sample_subject: Subject) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_compliance_subject(sample_subject)
    assert exc_info.value.status_code == 403


def test_get_admin_subject_delegates(sample_subject: Subject) -> None:
    admin = sample_subject.model_copy(update={"roles": ["PLATFORM_ADMIN"]})
    assert get_admin_subject(admin) is admin
