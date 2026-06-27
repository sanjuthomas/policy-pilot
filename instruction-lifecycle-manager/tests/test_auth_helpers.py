import base64

import pytest
from ilm.auth import (
    _decode_metadata_values,
    _parse_json_list,
    _parse_roles,
    _subject_from_metadata,
    _zitadel_request_headers,
)


def test_decode_metadata_values_base64() -> None:
    encoded = base64.b64encode(b"FICC").decode("ascii")
    result = _decode_metadata_values({"lob": encoded, "plain": "FX"})
    assert result["lob"] == "FICC"
    assert result["plain"] == "FX"


def test_decode_metadata_values_skips_non_string() -> None:
    assert _decode_metadata_values({"count": 1}) == {}


def test_parse_roles_json_array() -> None:
    assert _parse_roles('["A", "B"]') == ["A", "B"]


def test_parse_roles_comma_separated() -> None:
    assert _parse_roles("A, B") == ["A", "B"]


def test_parse_roles_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty or invalid"):
        _parse_roles("")


def test_parse_json_list_empty_array() -> None:
    assert _parse_json_list("[]") == []


def test_parse_json_list_invalid_returns_empty() -> None:
    assert _parse_json_list("not-json") == ["not-json"]


def test_subject_from_metadata_success() -> None:
    metadata = {
        "subject_user_id": "alice.ficc",
        "given_name": "Alice",
        "family_name": "Nguyen",
        "title": "VP",
        "roles": '["INSTRUCTION_CREATOR"]',
        "groups": '["MIDDLE_OFFICE"]',
        "lob": "FICC",
        "supervisor_id": "mgr.ficc",
    }
    subject = _subject_from_metadata(metadata, fallback_user_id=None)
    assert subject.user_id == "alice.ficc"
    assert subject.roles == ["INSTRUCTION_CREATOR"]
    assert subject.groups == ["MIDDLE_OFFICE"]


def test_subject_from_metadata_missing_user_id() -> None:
    with pytest.raises(ValueError, match="subject_user_id"):
        _subject_from_metadata({"title": "VP", "roles": '["R"]'}, fallback_user_id=None)


def test_subject_from_metadata_invalid_lob() -> None:
    with pytest.raises(ValueError, match="invalid lob"):
        _subject_from_metadata(
            {"subject_user_id": "u", "title": "VP", "roles": '["R"]', "lob": "BAD"},
            fallback_user_id=None,
        )


def test_zitadel_request_headers_without_issuer(monkeypatch) -> None:
    monkeypatch.setattr("ilm.auth.settings.oidc_issuer_url", None)
    assert _zitadel_request_headers() == {}
