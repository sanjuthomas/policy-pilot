from __future__ import annotations

import pytest
from fastapi import HTTPException

from etl.dependencies import get_subject


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
