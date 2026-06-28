from __future__ import annotations

from fastapi import Depends
from platform_auth import require_platform_admin

from ps.dependencies import get_subject
from ps.models.api import Subject


def get_admin_subject(subject: Subject = Depends(get_subject)) -> Subject:
    return require_platform_admin(subject)  # type: ignore[return-value]
