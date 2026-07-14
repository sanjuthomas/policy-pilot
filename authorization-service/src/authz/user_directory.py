from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from authz.models import SeedUser, Subject

_AMOUNT_CLUBS = frozenset(
    {
        "UP_TO_100_MILLION_CLUB",
        "UP_TO_1_BILLION_CLUB",
        "UP_TO_100_BILLION_CLUB",
    }
)


class SeedFile(BaseModel):
    defaults: dict[str, str] = Field(default_factory=dict)
    users: list[SeedUser]


def load_users(path: Path) -> SeedFile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeedFile.model_validate(raw)


class UserDirectory:
    """Loads approver candidates from the ZITADEL seed file."""

    def __init__(self, path: Path) -> None:
        self._seed = load_users(path)

    @property
    def email_domain(self) -> str:
        return self._seed.defaults.get("email_domain", "ssi.local")

    def all_users(self) -> list[SeedUser]:
        return sorted(self._seed.users, key=lambda user: user.user_id)

    def display_name_for(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        for user in self._seed.users:
            if user.user_id == user_id:
                return f"{user.family_name}, {user.given_name}"
        return user_id

    def funding_approver_candidates(self, owning_lob: str) -> list[Subject]:
        candidates: list[Subject] = []
        for user in self._seed.users:
            if "FUNDING_APPROVER" not in user.roles:
                continue
            if "MIDDLE_OFFICE" not in user.groups:
                continue
            if owning_lob not in user.covering_lobs:
                continue
            candidates.append(user.to_subject())
        candidates.sort(key=lambda subject: subject.user_id)
        return candidates

    def instruction_approver_candidates(self, owning_lob: str) -> list[Subject]:
        candidates: list[Subject] = []
        for user in self._seed.users:
            if "INSTRUCTION_APPROVER" not in user.roles:
                continue
            if user.lob != owning_lob:
                continue
            candidates.append(user.to_subject())
        candidates.sort(key=lambda subject: subject.user_id)
        return candidates

    def members_of_group(
        self,
        group: str,
        *,
        role: str | None = None,
        covering_lob: str | None = None,
    ) -> list[SeedUser]:
        """Return seed users whose ZITADEL groups include ``group`` (case-insensitive)."""
        group_upper = group.strip().upper()
        if not group_upper:
            return []

        role_upper = role.strip().upper() if role else None
        lob_upper = covering_lob.strip().upper() if covering_lob else None

        members: list[SeedUser] = []
        for user in self._seed.users:
            if group_upper not in {entry.upper() for entry in user.groups}:
                continue
            if role_upper and role_upper not in {entry.upper() for entry in user.roles}:
                continue
            if lob_upper and lob_upper not in {entry.upper() for entry in user.covering_lobs}:
                continue
            members.append(user)

        members.sort(key=lambda entry: entry.user_id)
        return members
