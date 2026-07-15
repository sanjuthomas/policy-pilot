from __future__ import annotations

import time
from collections.abc import Callable

from zitadel_directory.client import ZitadelDirectoryClient
from zitadel_directory.models import DirectoryUser


class DirectoryCache:
    """Process-local TTL cache over ``list_directory_users``.

    One implementation for authz / chat / harness so TTL and refresh semantics
    stay aligned across services.
    """

    def __init__(
        self,
        client_factory: Callable[[], ZitadelDirectoryClient],
        *,
        ttl_seconds: float = 60.0,
    ) -> None:
        self._client_factory = client_factory
        self._ttl_seconds = max(0.0, float(ttl_seconds))
        self._cache: list[DirectoryUser] | None = None
        self._cache_at = 0.0

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    def list_users(self, *, force_refresh: bool = False) -> list[DirectoryUser]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cache is not None
            and self._ttl_seconds > 0
            and (now - self._cache_at) < self._ttl_seconds
        ):
            return list(self._cache)

        users = self._client_factory().list_directory_users()
        self._cache = list(users)
        self._cache_at = now
        return list(users)

    def clear(self) -> None:
        self._cache = None
        self._cache_at = 0.0
