from __future__ import annotations

import pytest
from etl.dependencies import _subject_from_headers, get_subject
from etl.models import Subject
from fastapi import HTTPException


def test_get_subject_headers_mode() -> None:
    subject = get_subject(
        authorization=None,
        x_session_id=None,
        x_subject_user_id="admin-001",
        x_subject_title="Admin",
        x_subject_roles="PLATFORM_ADMIN",
        x_subject_lob=None,
        x_subject_supervisor_id=None,
        x_subject_groups=None,
        x_subject_covering_lobs=None,
    )
    assert subject.user_id == "admin-001"
    assert subject.roles == ["PLATFORM_ADMIN"]


def test_get_subject_headers_missing() -> None:
    with pytest.raises(HTTPException) as exc:
        get_subject(
            authorization=None,
            x_session_id=None,
            x_subject_user_id=None,
            x_subject_title="Admin",
            x_subject_roles="PLATFORM_ADMIN",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert exc.value.status_code == 401


def test_subject_from_headers_parses_groups_and_covering_lobs() -> None:
    subject = _subject_from_headers(
        "admin-001",
        "Admin",
        "PLATFORM_ADMIN,COMPLIANCE_ANALYST",
        "FICC",
        "sup-1",
        "grp-a,grp-b",
        "FICC,RATES",
    )
    assert subject.groups == ["grp-a", "grp-b"]
    assert subject.covering_lobs == ["FICC", "RATES"]


def test_subject_from_headers_rejects_empty_roles() -> None:
    with pytest.raises(HTTPException) as exc:
        _subject_from_headers("u1", "Title", " , ", None, None, None, None)
    assert exc.value.status_code == 400


def test_get_subject_jwt_mode(monkeypatch) -> None:
    monkeypatch.setattr("etl.dependencies.settings.auth_mode", "jwt")
    monkeypatch.setattr("etl.dependencies.settings.oidc_issuer_url", "http://issuer")
    subject = Subject(user_id="jwt-user", title="Analyst", roles=["COMPLIANCE_ANALYST"])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "etl.dependencies.subject_from_bearer_token",
            lambda token, session_id=None: subject,
        )
        result = get_subject(
            authorization="Bearer token-abc",
            x_session_id="sess-1",
            x_subject_user_id=None,
            x_subject_title=None,
            x_subject_roles=None,
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert result.user_id == "jwt-user"


def test_get_subject_jwt_missing_bearer(monkeypatch) -> None:
    monkeypatch.setattr("etl.dependencies.settings.auth_mode", "jwt")
    with pytest.raises(HTTPException) as exc:
        get_subject(
            authorization=None,
            x_session_id=None,
            x_subject_user_id="u1",
            x_subject_title="T",
            x_subject_roles="ROLE",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert exc.value.status_code == 401
