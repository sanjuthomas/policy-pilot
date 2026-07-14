from __future__ import annotations

from unittest.mock import patch

import pytest
from authz.evaluate_dependencies import resolve_evaluate_subject
from authz.models import Subject
from fastapi import HTTPException


def _subject(**overrides) -> Subject:
    base = dict(
        user_id="pay-201",
        title="Vice President",
        lob="FICC",
        roles=["FUNDING_APPROVER"],
        groups=["MIDDLE_OFFICE", "LIMIT_CLUB_100M"],
        supervisor_id="pay-301",
        covering_lobs=["FICC"],
    )
    base.update(overrides)
    return Subject(**base)


def test_resolve_evaluate_subject_requires_obo() -> None:
    with pytest.raises(HTTPException) as exc:
        resolve_evaluate_subject(
            service_token="svc-token",
            service_session_id="svc-sess",
            x_on_behalf_of=None,
            x_on_behalf_of_session_id=None,
            inline_subject=_subject(),
        )
    assert exc.value.status_code == 401
    assert "X-On-Behalf-Of" in str(exc.value.detail)


def test_resolve_evaluate_subject_obo_without_inline() -> None:
    token_subject = _subject().model_copy(
        update={"delegated_by": "svc-payment", "delegated_by_roles": ["INSTRUCTION_MARKER"]}
    )
    with patch(
        "authz.evaluate_dependencies.subject_from_obo_call",
        return_value=token_subject,
    ):
        resolved = resolve_evaluate_subject(
            service_token="svc-token",
            service_session_id="svc-sess",
            x_on_behalf_of="user-token",
            x_on_behalf_of_session_id="user-sess",
            inline_subject=None,
        )
    assert resolved.user_id == "pay-201"
    assert resolved.delegated_by == "svc-payment"


def test_resolve_evaluate_subject_rejects_mismatched_inline() -> None:
    token_subject = _subject()
    inline = _subject(user_id="pay-999", roles=["PAYMENT_CREATOR"])
    with patch(
        "authz.evaluate_dependencies.subject_from_obo_call",
        return_value=token_subject,
    ):
        with pytest.raises(HTTPException) as exc:
            resolve_evaluate_subject(
                service_token="svc-token",
                service_session_id=None,
                x_on_behalf_of="user-token",
                x_on_behalf_of_session_id=None,
                inline_subject=inline,
            )
    assert exc.value.status_code == 403
    assert "user_id" in str(exc.value.detail)
    assert "roles" in str(exc.value.detail)


def test_resolve_evaluate_subject_accepts_matching_inline() -> None:
    token_subject = _subject().model_copy(
        update={"delegated_by": "svc-payment", "delegated_by_roles": ["R"]}
    )
    inline = _subject()  # no delegated_by — identity still matches
    with patch(
        "authz.evaluate_dependencies.subject_from_obo_call",
        return_value=token_subject,
    ):
        resolved = resolve_evaluate_subject(
            service_token="svc-token",
            service_session_id=None,
            x_on_behalf_of="Bearer user-token",
            x_on_behalf_of_session_id=None,
            inline_subject=inline,
        )
    assert resolved.user_id == "pay-201"
    assert resolved.delegated_by == "svc-payment"
