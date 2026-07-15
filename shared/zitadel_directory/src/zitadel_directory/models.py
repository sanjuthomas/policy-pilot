from __future__ import annotations

from pydantic import BaseModel, Field


class DirectoryUser(BaseModel):
    """Business user projected from ZITADEL profile + metadata."""

    user_id: str
    given_name: str
    family_name: str
    title: str
    roles: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    lob: str | None = None
    supervisor_id: str | None = None
    covering_lobs: list[str] = Field(default_factory=list)
    zitadel_user_id: str | None = None
