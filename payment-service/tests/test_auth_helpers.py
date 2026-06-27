from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from ps.auth import (
    _decode_metadata_values,
    _parse_json_list,
    _subject_from_metadata,
    _zitadel_request_headers,
    subject_from_bearer_token,
)


def test_decode_metadata_values_decodes_base64() -> None:
    raw = {"title": base64.b64encode(b"VP Finance").decode("ascii")}
    decoded = _decode_metadata_values(raw)
    assert decoded["title"] == "VP Finance"


def test_decode_metadata_values_keeps_plain_strings() -> None:
    raw = {"title": "plain-title", "count": 42}
    decoded = _decode_metadata_values(raw)
    assert decoded["title"] == "plain-title"
    assert "count" not in decoded


def test_decode_metadata_values_invalid_base64_falls_back() -> None:
    raw = {"title": "not-valid-base64!!!"}
    decoded = _decode_metadata_values(raw)
    assert decoded["title"] == "not-valid-base64!!!"


def test_parse_json_list_from_json_array() -> None:
    assert _parse_json_list(json.dumps(["A", "B"])) == ["A", "B"]


def test_parse_json_list_from_comma_separated() -> None:
    assert _parse_json_list("A, B, C") == ["A", "B", "C"]


def test_parse_json_list_invalid_json_non_list_returns_empty() -> None:
    assert _parse_json_list(json.dumps({"roles": "x"})) == []


def test_parse_json_list_invalid_json_scalar_returns_empty() -> None:
    assert _parse_json_list(json.dumps("solo")) == []


def test_subject_from_metadata_full() -> None:
    metadata = {
        "subject_user_id": "alice",
        "given_name": "Alice",
        "family_name": "Smith",
        "title": "VP Finance",
        "lob": "CORP",
        "roles": json.dumps(["PAYMENT_CREATOR"]),
        "groups": json.dumps(["MIDDLE_OFFICE"]),
        "covering_lobs": json.dumps(["CORP"]),
        "supervisor_id": "boss1",
    }
    subject = _subject_from_metadata(metadata, fallback_user_id="fallback")
    assert subject.user_id == "alice"
    assert subject.given_name == "Alice"
    assert subject.family_name == "Smith"
    assert subject.title == "VP Finance"
    assert subject.roles == ["PAYMENT_CREATOR"]
    assert subject.groups == ["MIDDLE_OFFICE"]
    assert subject.covering_lobs == ["CORP"]
    assert subject.supervisor_id == "boss1"


def test_subject_from_metadata_uses_fallback_user_id() -> None:
    metadata = {
        "title": "VP",
        "roles": "PAYMENT_CREATOR",
    }
    subject = _subject_from_metadata(metadata, fallback_user_id="from-token")
    assert subject.user_id == "from-token"


def test_subject_from_metadata_missing_user_id() -> None:
    with pytest.raises(ValueError, match="missing subject_user_id"):
        _subject_from_metadata({"title": "VP", "roles": "PAYMENT_CREATOR"}, fallback_user_id=None)


def test_subject_from_metadata_missing_title() -> None:
    with pytest.raises(ValueError, match="missing title"):
        _subject_from_metadata({"subject_user_id": "u1", "roles": "PAYMENT_CREATOR"}, fallback_user_id=None)


def test_subject_from_metadata_missing_roles() -> None:
    with pytest.raises(ValueError, match="missing roles"):
        _subject_from_metadata({"subject_user_id": "u1", "title": "VP"}, fallback_user_id=None)


def test_subject_from_metadata_empty_roles() -> None:
    with pytest.raises(ValueError, match="roles claim is empty"):
        _subject_from_metadata(
            {"subject_user_id": "u1", "title": "VP", "roles": "  "},
            fallback_user_id=None,
        )


def test_zitadel_request_headers_with_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.auth.settings.oidc_issuer_url", "https://auth.example.com")
    assert _zitadel_request_headers() == {"Host": "auth.example.com"}


def test_zitadel_request_headers_without_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.auth.settings.oidc_issuer_url", None)
    assert _zitadel_request_headers() == {}


def test_subject_from_bearer_token_via_jwt_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = {
        "subject_user_id": "alice",
        "title": "VP",
        "roles": '["PAYMENT_CREATOR"]',
    }
    monkeypatch.setattr("ps.auth.settings.oidc_issuer_url", "https://auth.example.com")
    monkeypatch.setattr("ps.auth.settings.oidc_audience", None)

    mock_jwks = MagicMock()
    mock_jwks.get_signing_key_from_jwt.return_value = MagicMock(key="secret")

    with patch("ps.auth._jwks_client", return_value=mock_jwks), patch(
        "ps.auth.jwt.decode",
        return_value={
            "preferred_username": "alice",
            "urn:zitadel:iam:user:metadata": metadata,
        },
    ):
        subject = subject_from_bearer_token("token")

    assert subject.user_id == "alice"
    assert subject.roles == ["PAYMENT_CREATOR"]


def test_subject_from_bearer_token_via_userinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ps.auth.settings.oidc_issuer_url", "https://auth.example.com")
    monkeypatch.setattr("ps.auth.settings.oidc_audience", None)

    mock_jwks = MagicMock()
    mock_jwks.get_signing_key_from_jwt.side_effect = RuntimeError("bad jwt")

    userinfo_metadata = {
        "subject_user_id": "bob",
        "title": "MD",
        "roles": '["FUNDING_APPROVER"]',
    }

    with patch("ps.auth._jwks_client", return_value=mock_jwks), patch(
        "ps.auth._fetch_userinfo_metadata",
        return_value=userinfo_metadata,
    ):
        subject = subject_from_bearer_token("token")

    assert subject.user_id == "bob"
