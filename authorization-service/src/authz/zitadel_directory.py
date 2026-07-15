from __future__ import annotations

from urllib.parse import urlparse

from zitadel_directory import DirectoryUser, ZitadelDirectoryClient

from authz.config import settings
from authz.models import SeedUser


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


def _directory_client() -> ZitadelDirectoryClient:
    if not settings.zitadel_service_pat:
        raise RuntimeError("zitadel service PAT is not configured")
    client = ZitadelDirectoryClient(
        base_url=_zitadel_base_url(),
        pat=settings.zitadel_service_pat,
        host_header=_host_header(),
    )
    try:
        return client.with_org()
    except Exception:
        # Org header is optional for some deployments; fall back to unscoped client.
        return client


def _to_seed_user(user: DirectoryUser) -> SeedUser:
    return SeedUser(
        user_id=user.user_id,
        given_name=user.given_name,
        family_name=user.family_name,
        title=user.title,
        roles=list(user.roles),
        groups=list(user.groups),
        lob=user.lob,
        supervisor_id=user.supervisor_id,
        covering_lobs=list(user.covering_lobs),
    )


def load_seed_users_from_zitadel() -> list[SeedUser]:
    """Fetch the live human-user directory from ZITADEL."""
    return [_to_seed_user(user) for user in _directory_client().list_directory_users()]
