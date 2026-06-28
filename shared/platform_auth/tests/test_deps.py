from __future__ import annotations

import pytest
from fastapi import HTTPException

from platform_auth.deps import is_platform_admin, require_platform_admin


class _Subject:
    def __init__(self, *, roles: list[str] | None = None, groups: list[str] | None = None) -> None:
        self.roles = roles or []
        self.groups = groups or []


def test_is_platform_admin_by_role() -> None:
    subject = _Subject(roles=["PLATFORM_ADMIN"])
    assert is_platform_admin(subject) is True


def test_is_platform_admin_by_group() -> None:
    subject = _Subject(roles=["OTHER"], groups=["ADMIN"])
    assert is_platform_admin(subject) is True


def test_is_platform_admin_false() -> None:
    subject = _Subject(roles=["COMPLIANCE_ANALYST"])
    assert is_platform_admin(subject) is False


def test_require_platform_admin_returns_subject() -> None:
    subject = _Subject(roles=["PLATFORM_ADMIN"])
    assert require_platform_admin(subject) is subject


def test_require_platform_admin_raises() -> None:
    subject = _Subject(roles=["PAYMENT_CREATOR"])
    with pytest.raises(HTTPException) as exc:
        require_platform_admin(subject)
    assert exc.value.status_code == 403
