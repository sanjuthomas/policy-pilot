from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SeedUser(BaseModel):
    user_id: str
    given_name: str
    family_name: str
    title: str
    roles: list[str]


class SeedFile(BaseModel):
    defaults: dict[str, str] = Field(default_factory=dict)
    users: list[SeedUser]


def load_users(path: Path) -> SeedFile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeedFile.model_validate(raw)


def compliance_users(
    path: Path,
    *,
    allowed_roles: set[str] | None = None,
    compliance_role: str = "COMPLIANCE_ANALYST",
) -> list[SeedUser]:
    """Users who may sign in to chat / policy inquiry UIs."""
    roles = allowed_roles if allowed_roles is not None else {compliance_role}
    seed = load_users(path)
    return [user for user in seed.users if roles.intersection(user.roles)]
