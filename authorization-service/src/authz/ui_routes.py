from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from authz.admin import get_admin_subject
from authz.directory import build_user_directory_rows
from authz.models import UserDirectoryResponse

STATIC_DIR = Path(__file__).resolve().parent / "static"

router = APIRouter(tags=["ui"])


def _user_directory():
    from authz.main import user_directory

    if user_directory is None:
        raise HTTPException(status_code=503, detail="user directory not ready")
    return user_directory


@router.get("/ui")
@router.get("/ui/")
async def ui_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/api/ui/users", response_model=UserDirectoryResponse)
async def ui_list_users(
    q: str | None = Query(default=None, description="Filter by user id, name, role, or group"),
    role: str | None = Query(default=None),
    group: str | None = Query(default=None),
    _admin=Depends(get_admin_subject),
) -> UserDirectoryResponse:
    directory = _user_directory()
    rows = build_user_directory_rows(directory)

    if role:
        role_upper = role.upper()
        rows = [row for row in rows if role_upper in row.roles]

    if group:
        group_upper = group.upper()
        rows = [
            row
            for row in rows
            if group_upper in row.groups
            or group_upper in row.amount_clubs
            or group_upper in row.covering_lobs
        ]

    if q:
        needle = q.strip().lower()
        if needle:
            rows = [
                row
                for row in rows
                if needle in row.user_id.lower()
                or needle in row.display_name.lower()
                or needle in row.login_name.lower()
                or needle in row.title.lower()
                or any(needle in value.lower() for value in row.roles)
                or any(needle in value.lower() for value in row.groups)
                or any(needle in value.lower() for value in row.amount_clubs)
                or any(needle in value.lower() for value in row.covering_lobs)
                or (row.lob and needle in row.lob.lower())
                or (row.supervisor_id and needle in row.supervisor_id.lower())
            ]

    return UserDirectoryResponse(
        count=len(rows),
        email_domain=directory.email_domain,
        users=rows,
    )
