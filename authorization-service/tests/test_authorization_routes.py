from __future__ import annotations

import pytest
from fastapi import HTTPException

from authz.evaluate_dependencies import resolve_evaluate_subject
from authz.models import Subject


def test_resolve_evaluate_subject_requires_inline_when_no_obo() -> None:
    with pytest.raises(HTTPException) as exc:
        resolve_evaluate_subject(
            service_token="svc-token",
            service_session_id="sess-1",
            x_on_behalf_of=None,
            x_on_behalf_of_session_id=None,
            inline_subject=None,
        )
    assert exc.value.status_code == 400


def test_resolve_evaluate_subject_accepts_inline_subject() -> None:
    subject = Subject(user_id="alice", title="VP", roles=["INSTRUCTION_CREATOR"])
    resolved = resolve_evaluate_subject(
        service_token="svc-token",
        service_session_id="sess-1",
        x_on_behalf_of=None,
        x_on_behalf_of_session_id=None,
        inline_subject=subject,
    )
    assert resolved.user_id == "alice"
