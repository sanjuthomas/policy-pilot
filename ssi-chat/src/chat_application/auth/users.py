from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, Field
from zitadel_directory import DirectoryCache, DirectoryUser, build_directory_client

from chat_application.auth.capabilities import audience_labels
from chat_application.config import settings

_CACHE: DirectoryCache | None = None


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


def _to_seed_user(user: DirectoryUser) -> SeedUser:
    return SeedUser(**user.seed_fields())


def _directory_cache() -> DirectoryCache:
    global _CACHE
    if _CACHE is None:
        if not settings.zitadel_service_pat:
            raise RuntimeError("ZITADEL service PAT is not configured")
        base_url = (
            settings.zitadel_internal_url
            or settings.oidc_internal_url
            or settings.zitadel_url
        ).rstrip("/")
        host = settings.zitadel_host_header or (
            urlparse(settings.oidc_issuer_url).netloc if settings.oidc_issuer_url else None
        )
        pat = settings.zitadel_service_pat

        def _client():
            return build_directory_client(
                base_url=base_url,
                pat=pat or "",
                host_header=host,
            )

        _CACHE = DirectoryCache(
            _client,
            ttl_seconds=settings.user_directory_cache_ttl_seconds,
        )
    return _CACHE


def load_users(*, force_refresh: bool = False) -> SeedFile:
    """Load the live user directory from ZITADEL (shared DirectoryCache)."""
    users = [
        _to_seed_user(user)
        for user in _directory_cache().list_users(force_refresh=force_refresh)
    ]
    return SeedFile(
        defaults={"email_domain": settings.email_domain},
        users=users,
    )


def compliance_users(
    *,
    allowed_roles: set[str] | None = None,
    compliance_role: str = "COMPLIANCE_ANALYST",
    seed: SeedFile | None = None,
) -> list[SeedUser]:
    """Users who may sign in to chat / policy inquiry UIs (legacy helper)."""
    roles = allowed_roles if allowed_roles is not None else {compliance_role}
    roster = seed or load_users()
    return [user for user in roster.users if roles.intersection(user.roles)]


def chat_users(
    *,
    allowed_roles: set[str],
    seed: SeedFile | None = None,
) -> list[dict[str, object]]:
    """Chat-eligible directory users with audience labels for the login picker."""
    roster = seed or load_users()
    rows: list[dict[str, object]] = []
    for user in roster.users:
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


def clear_directory_cache() -> None:
    global _CACHE
    if _CACHE is not None:
        _CACHE.clear()
