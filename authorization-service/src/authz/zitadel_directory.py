from __future__ import annotations

from urllib.parse import urlparse

from zitadel_directory import DirectoryCache, DirectoryUser, build_directory_client

from authz.config import settings
from authz.models import SeedUser

_CACHE: DirectoryCache | None = None


def _zitadel_base_url() -> str:
    if settings.zitadel_internal_url:
        return settings.zitadel_internal_url.rstrip("/")
    if settings.oidc_internal_url:
        return settings.oidc_internal_url.rstrip("/")
    if settings.oidc_issuer_url:
        return settings.oidc_issuer_url.rstrip("/")
    raise RuntimeError("ZITADEL URL is not configured")


def _host_header() -> str | None:
    if settings.oidc_issuer_url:
        host = urlparse(settings.oidc_issuer_url).netloc
        return host or None
    return None


def _directory_cache() -> DirectoryCache:
    global _CACHE
    if _CACHE is None:
        if not settings.zitadel_service_pat:
            raise RuntimeError("zitadel service PAT is not configured")

        def _client():
            return build_directory_client(
                base_url=_zitadel_base_url(),
                pat=settings.zitadel_service_pat or "",
                host_header=_host_header(),
            )

        _CACHE = DirectoryCache(
            _client,
            ttl_seconds=settings.user_directory_cache_ttl_seconds,
        )
    return _CACHE


def _to_seed_user(user: DirectoryUser) -> SeedUser:
    return SeedUser(**user.seed_fields())


def load_seed_users_from_zitadel(*, force_refresh: bool = False) -> list[SeedUser]:
    """Fetch the live human-user directory from ZITADEL (shared cache)."""
    return [
        _to_seed_user(user)
        for user in _directory_cache().list_users(force_refresh=force_refresh)
    ]


def clear_directory_cache() -> None:
    if _CACHE is not None:
        _CACHE.clear()
