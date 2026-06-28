from __future__ import annotations

from fastapi import HTTPException

ADMIN_ROLE = "PLATFORM_ADMIN"
ADMIN_GROUP = "ADMIN"


def is_platform_admin(subject: object) -> bool:
    roles = getattr(subject, "roles", None) or []
    groups = getattr(subject, "groups", None) or []
    return ADMIN_ROLE in roles or ADMIN_GROUP in groups


def require_platform_admin(subject: object) -> object:
    if not is_platform_admin(subject):
        raise HTTPException(
            status_code=403,
            detail="PLATFORM_ADMIN role or ADMIN group required",
        )
    return subject
