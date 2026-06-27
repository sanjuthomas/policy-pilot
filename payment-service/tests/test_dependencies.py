from __future__ import annotations

import pytest
from fastapi import HTTPException
from ps.dependencies import _subject_from_headers, get_subject


def test_subject_from_headers_minimal() -> None:
    subject = _subject_from_headers(
        x_subject_user_id="alice",
        x_subject_title="VP Finance",
        x_subject_roles="PAYMENT_CREATOR,FUNDING_APPROVER",
        x_subject_lob=None,
        x_subject_supervisor_id=None,
        x_subject_groups=None,
        x_subject_covering_lobs=None,
    )
    assert subject.user_id == "alice"
    assert subject.title == "VP Finance"
    assert subject.roles == ["PAYMENT_CREATOR", "FUNDING_APPROVER"]
    assert subject.groups == []
    assert subject.covering_lobs == []
    assert subject.lob is None


def test_subject_from_headers_all_fields() -> None:
    subject = _subject_from_headers(
        x_subject_user_id="bob",
        x_subject_title="MD",
        x_subject_roles="FUNDING_APPROVER",
        x_subject_lob="CORP",
        x_subject_supervisor_id="ceo",
        x_subject_groups="MIDDLE_OFFICE, TREASURY",
        x_subject_covering_lobs="CORP, RETAIL",
    )
    assert subject.lob == "CORP"
    assert subject.supervisor_id == "ceo"
    assert subject.groups == ["MIDDLE_OFFICE", "TREASURY"]
    assert subject.covering_lobs == ["CORP", "RETAIL"]


def test_subject_from_headers_strips_whitespace() -> None:
    subject = _subject_from_headers(
        x_subject_user_id="alice",
        x_subject_title="VP",
        x_subject_roles=" PAYMENT_CREATOR , FUNDING_APPROVER ",
        x_subject_lob=None,
        x_subject_supervisor_id=None,
        x_subject_groups=" MIDDLE_OFFICE ",
        x_subject_covering_lobs=" CORP ",
    )
    assert subject.roles == ["PAYMENT_CREATOR", "FUNDING_APPROVER"]
    assert subject.groups == ["MIDDLE_OFFICE"]
    assert subject.covering_lobs == ["CORP"]


def test_subject_from_headers_rejects_empty_roles() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _subject_from_headers(
            x_subject_user_id="alice",
            x_subject_title="VP",
            x_subject_roles="  ,  ",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert exc_info.value.status_code == 400
    assert "Roles must not be empty" in exc_info.value.detail


def test_get_subject_headers_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.dependencies.settings.auth_mode", "headers")
    subject = get_subject(
        authorization=None,
        x_session_id=None,
        x_subject_user_id="alice",
        x_subject_title="VP",
        x_subject_roles="PAYMENT_CREATOR",
        x_subject_lob="CORP",
        x_subject_supervisor_id=None,
        x_subject_groups=None,
        x_subject_covering_lobs=None,
    )
    assert subject.user_id == "alice"


def test_get_subject_headers_mode_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.dependencies.settings.auth_mode", "headers")
    with pytest.raises(HTTPException) as exc_info:
        get_subject(
            authorization=None,
            x_session_id=None,
            x_subject_user_id=None,
            x_subject_title="VP",
            x_subject_roles="PAYMENT_CREATOR",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert exc_info.value.status_code == 401
    assert "X-Subject-User-Id" in exc_info.value.detail


def test_get_subject_jwt_mode_requires_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.dependencies.settings.auth_mode", "jwt")
    with pytest.raises(HTTPException) as exc_info:
        get_subject(
            authorization=None,
            x_session_id=None,
            x_subject_user_id="alice",
            x_subject_title="VP",
            x_subject_roles="PAYMENT_CREATOR",
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert exc_info.value.status_code == 401
    assert "Bearer token required" in exc_info.value.detail


def test_get_subject_jwt_mode_missing_oidc_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.dependencies.settings.auth_mode", "jwt")
    monkeypatch.setattr("ps.dependencies.settings.oidc_issuer_url", None)
    with pytest.raises(HTTPException) as exc_info:
        get_subject(
            authorization="Bearer token",
            x_session_id=None,
            x_subject_user_id=None,
            x_subject_title=None,
            x_subject_roles=None,
            x_subject_lob=None,
            x_subject_supervisor_id=None,
            x_subject_groups=None,
            x_subject_covering_lobs=None,
        )
    assert exc_info.value.status_code == 500
    assert "OIDC issuer" in exc_info.value.detail


def test_get_subject_auto_mode_uses_headers_without_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ps.dependencies.settings.auth_mode", "auto")
    subject = get_subject(
        authorization=None,
        x_session_id=None,
        x_subject_user_id="alice",
        x_subject_title="VP",
        x_subject_roles="PAYMENT_CREATOR",
        x_subject_lob=None,
        x_subject_supervisor_id=None,
        x_subject_groups=None,
        x_subject_covering_lobs=None,
    )
    assert subject.user_id == "alice"
