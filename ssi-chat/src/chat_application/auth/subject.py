from __future__ import annotations

from pydantic import BaseModel, Field


class Subject(BaseModel):
    user_id: str
    given_name: str | None = None
    family_name: str | None = None
    title: str
    lob: str | None = None
    roles: list[str] = Field(min_length=1)
    groups: list[str] = Field(default_factory=list)
    supervisor_id: str | None = None
    covering_lobs: list[str] = Field(default_factory=list)
