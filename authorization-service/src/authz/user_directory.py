from __future__ import annotations

import time
from collections.abc import Callable
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
    """YAML seed shape — used only by tests/helpers, not production loaders."""

    defaults: dict[str, str] = Field(default_factory=dict)
    users: list[SeedUser]


def load_users(path: Path) -> SeedFile:
    """Parse a seed YAML file (test helper). Runtime directory loads come from ZITADEL."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeedFile.model_validate(raw)


class UserDirectory:
    """In-memory directory snapshot with optional ZITADEL refresh provider."""

    def __init__(
        self,
        users: list[SeedUser] | None = None,
        *,
        email_domain: str = "ssi.local",
        provider: Callable[[], list[SeedUser]] | None = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        if users is None and provider is None:
            raise ValueError("UserDirectory requires users= or provider=")
        if users is not None and provider is not None:
            raise ValueError("UserDirectory accepts users= or provider=, not both")
        self._static_users = (
            sorted(users, key=lambda user: user.user_id) if users is not None else None
        )
        self._provider = provider
        self._email_domain = email_domain
        self._cache_ttl_seconds = max(0.0, cache_ttl_seconds)
        self._cache: list[SeedUser] | None = None
        self._cache_at = 0.0

    @classmethod
    def from_users(
        cls,
        users: list[SeedUser],
        *,
        email_domain: str = "ssi.local",
    ) -> UserDirectory:
        return cls(users=users, email_domain=email_domain)

    @classmethod
    def from_yaml(cls, path: Path) -> UserDirectory:
        """Load a frozen snapshot from seed YAML (tests / offline fixtures only)."""
        seed = load_users(path)
        return cls.from_users(
            seed.users,
            email_domain=seed.defaults.get("email_domain", "ssi.local"),
        )

    @classmethod
    def from_zitadel(
        cls,
        *,
        email_domain: str = "ssi.local",
        cache_ttl_seconds: float = 60.0,
        provider: Callable[[], list[SeedUser]] | None = None,
    ) -> UserDirectory:
        from authz.zitadel_directory import load_seed_users_from_zitadel

        # Shared DirectoryCache owns TTL for the default ZITADEL provider;
        # avoid a second cache layer in UserDirectory for that path.
        if provider is None:
            return cls(
                email_domain=email_domain,
                provider=load_seed_users_from_zitadel,
                cache_ttl_seconds=0.0,
            )
        return cls(
            email_domain=email_domain,
            provider=provider,
            cache_ttl_seconds=cache_ttl_seconds,
        )

    @property
    def email_domain(self) -> str:
        return self._email_domain

    def _users(self) -> list[SeedUser]:
        if self._static_users is not None:
            return self._static_users
        assert self._provider is not None
        now = time.monotonic()
        if (
            self._cache is not None
            and self._cache_ttl_seconds > 0
            and (now - self._cache_at) < self._cache_ttl_seconds
        ):
            return self._cache
        users = sorted(self._provider(), key=lambda user: user.user_id)
        self._cache = users
        self._cache_at = now
        return users

    def all_users(self) -> list[SeedUser]:
        return list(self._users())

    def display_name_for(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        for user in self._users():
            if user.user_id == user_id:
                return f"{user.family_name}, {user.given_name}"
        return user_id

    def funding_approver_candidates(self, owning_lob: str) -> list[Subject]:
        candidates: list[Subject] = []
        for user in self._users():
            if "FUNDING_APPROVER" not in user.roles:
                continue
            if "MIDDLE_OFFICE" not in user.groups:
                continue
            if owning_lob not in user.covering_lobs:
                continue
            candidates.append(user.to_subject())
        candidates.sort(key=lambda subject: subject.user_id)
        return candidates

    def payment_submitter_candidates(self, owning_lob: str) -> list[Subject]:
        """Front-office desk analysts who may SUBMIT drafts for ``owning_lob``."""
        candidates: list[Subject] = []
        for user in self._users():
            if "PAYMENT_CREATOR" not in user.roles:
                continue
            if not user.lob or user.lob != owning_lob:
                continue
            candidates.append(user.to_subject())
        candidates.sort(key=lambda subject: subject.user_id)
        return candidates

    def instruction_approver_candidates(self, owning_lob: str) -> list[Subject]:
        candidates: list[Subject] = []
        for user in self._users():
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
        """Return users whose ZITADEL groups include ``group`` (case-insensitive)."""
        group_upper = group.strip().upper()
        if not group_upper:
            return []

        role_upper = role.strip().upper() if role else None
        lob_upper = covering_lob.strip().upper() if covering_lob else None

        members: list[SeedUser] = []
        for user in self._users():
            if group_upper not in {entry.upper() for entry in user.groups}:
                continue
            if role_upper and role_upper not in {entry.upper() for entry in user.roles}:
                continue
            if lob_upper and lob_upper not in {entry.upper() for entry in user.covering_lobs}:
                continue
            members.append(user)

        members.sort(key=lambda entry: entry.user_id)
        return members

    def users_with_role(self, role: str) -> list[SeedUser]:
        role_upper = role.strip().upper()
        if not role_upper:
            return []
        matches = [
            user
            for user in self._users()
            if role_upper in {entry.upper() for entry in user.roles}
        ]
        matches.sort(key=lambda entry: entry.user_id)
        return matches

    def users_covering_lob(self, covering_lob: str) -> list[SeedUser]:
        lob_upper = covering_lob.strip().upper()
        if not lob_upper:
            return []
        matches = [
            user
            for user in self._users()
            if lob_upper in {entry.upper() for entry in user.covering_lobs}
        ]
        matches.sort(key=lambda entry: entry.user_id)
        return matches
