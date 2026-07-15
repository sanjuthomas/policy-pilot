from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from zitadel_directory import DirectoryUser, ZitadelDirectoryClient

from chat_application.auth.capabilities import audience_labels
from chat_application.config import settings

logger = logging.getLogger(__name__)

_CACHE: list[SeedUser] | None = None
_CACHE_AT = 0.0


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
    return SeedUser(
        user_id=user.user_id,
        given_name=user.given_name,
        family_name=user.family_name,
        title=user.title,
        roles=list(user.roles),
        lob=user.lob,
        groups=list(user.groups),
        covering_lobs=list(user.covering_lobs),
        supervisor_id=user.supervisor_id,
    )


def _directory_client() -> ZitadelDirectoryClient:
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
    client = ZitadelDirectoryClient(
        base_url=base_url,
        pat=settings.zitadel_service_pat,
        host_header=host,
    )
    try:
        return client.with_org()
    except Exception:
        logger.warning("directory client continuing without org header", exc_info=True)
        return client


def load_users(*, force_refresh: bool = False) -> SeedFile:
    """Load the live user directory from ZITADEL (cached)."""
    global _CACHE, _CACHE_AT

    ttl = max(0.0, float(settings.user_directory_cache_ttl_seconds))
    now = time.monotonic()
    if (
        not force_refresh
        and _CACHE is not None
        and ttl > 0
        and (now - _CACHE_AT) < ttl
    ):
        return SeedFile(
            defaults={"email_domain": settings.email_domain},
            users=list(_CACHE),
        )

    users = [_to_seed_user(user) for user in _directory_client().list_directory_users()]
    _CACHE = users
    _CACHE_AT = now
    return SeedFile(
        defaults={"email_domain": settings.email_domain},
        users=list(users),
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
    global _CACHE, _CACHE_AT
    _CACHE = None
    _CACHE_AT = 0.0
