import pytest
from fastapi import HTTPException
from inst.dependencies import _subject_from_headers


def test_subject_from_headers_success() -> None:
    subject = _subject_from_headers(
        x_subject_user_id="alice.ficc",
        x_subject_title="Vice President",
        x_subject_roles="INSTRUCTION_CREATOR, MIDDLE_OFFICE",
        x_subject_lob="FICC",
        x_subject_supervisor_id="mgr.ficc",
    )
    assert subject.user_id == "alice.ficc"
    assert subject.roles == ["INSTRUCTION_CREATOR", "MIDDLE_OFFICE"]
    assert subject.lob == "FICC"
    assert subject.supervisor_id == "mgr.ficc"


def test_subject_from_headers_empty_roles_raises() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _subject_from_headers(
            x_subject_user_id="u",
            x_subject_title="VP",
            x_subject_roles="  ,  ",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
        )
    assert exc_info.value.status_code == 400
    assert "Roles" in exc_info.value.detail


def test_subject_from_headers_invalid_lob_raises() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _subject_from_headers(
            x_subject_user_id="u",
            x_subject_title="VP",
            x_subject_roles="INSTRUCTION_CREATOR",
            x_subject_lob="INVALID",
            x_subject_supervisor_id=None,
        )
    assert exc_info.value.status_code == 400
    assert "X-Subject-Lob" in exc_info.value.detail
