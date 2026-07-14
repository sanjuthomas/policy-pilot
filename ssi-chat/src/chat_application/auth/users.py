from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from chat_application.auth.capabilities import audience_labels


class SeedUser(BaseModel):
    user_id: str
    given_name: str
    family_name: str
    title: str
    roles: list[str]
    lob: str | None = None
    groups: list[str] = Field(default_factory=list)
    covering_lobs: list[str] = Field(default_factory=list)
    supervisor_id: str | None = None


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
    """Users who may sign in to chat / policy inquiry UIs (legacy helper)."""
    roles = allowed_roles if allowed_roles is not None else {compliance_role}
    seed = load_users(path)
    return [user for user in seed.users if roles.intersection(user.roles)]


def chat_users(
    path: Path,
    *,
    allowed_roles: set[str],
) -> list[dict[str, object]]:
    """Chat-eligible seed users with audience labels for the login picker."""
    seed = load_users(path)
    rows: list[dict[str, object]] = []
    for user in seed.users:
        if user.user_id.startswith("svc-"):
            continue
        if not allowed_roles.intersection(user.roles):
            continue
        rows.append(
            {
                "user_id": user.user_id,
                "display_name": f"{user.family_name}, {user.given_name}",
                "title": user.title,
                "roles": list(user.roles),
                "audiences": audience_labels(user.roles),
            }
        )
    rows.sort(key=lambda row: str(row["display_name"]))
    return rows
