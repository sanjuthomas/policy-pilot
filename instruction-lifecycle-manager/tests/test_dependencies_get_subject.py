import pytest
from fastapi import HTTPException
from ilm.dependencies import get_subject


def test_get_subject_headers_mode(monkeypatch) -> None:
    monkeypatch.setattr("ilm.dependencies.settings.auth_mode", "headers")
    subject = get_subject(
        authorization=None,
        x_session_id=None,
        x_on_behalf_of=None,
        x_on_behalf_of_session_id=None,
        x_subject_user_id="alice.ficc",
        x_subject_title="VP",
        x_subject_roles="INSTRUCTION_CREATOR",
        x_subject_lob="FICC",
        x_subject_supervisor_id=None,
    )
    assert subject.user_id == "alice.ficc"


def test_get_subject_headers_missing_raises(monkeypatch) -> None:
    monkeypatch.setattr("ilm.dependencies.settings.auth_mode", "headers")
    with pytest.raises(HTTPException) as exc_info:
        get_subject(
            authorization=None,
            x_session_id=None,
            x_on_behalf_of=None,
            x_on_behalf_of_session_id=None,
            x_subject_user_id=None,
            x_subject_title="VP",
            x_subject_roles="R",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
        )
    assert exc_info.value.status_code == 401


def test_get_subject_jwt_mode_requires_bearer(monkeypatch) -> None:
    monkeypatch.setattr("ilm.dependencies.settings.auth_mode", "jwt")
    with pytest.raises(HTTPException) as exc_info:
        get_subject(
            authorization=None,
            x_session_id=None,
            x_on_behalf_of=None,
            x_on_behalf_of_session_id=None,
            x_subject_user_id="u",
            x_subject_title="VP",
            x_subject_roles="R",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
        )
    assert exc_info.value.status_code == 401
