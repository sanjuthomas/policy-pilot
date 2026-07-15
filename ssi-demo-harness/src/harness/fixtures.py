from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field
from zitadel_directory import DirectoryUser, ZitadelDirectoryClient

from harness.config import Settings
from harness.config import settings as default_settings

logger = logging.getLogger(__name__)

_CACHE = None
_CACHE_AT = 0.0


class SeedUser(BaseModel):
    user_id: str
    given_name: str
    family_name: str
    title: str
    roles: list[str]
    groups: list[str] = Field(default_factory=list)
    lob: str | None = None
    supervisor_id: str | None = None
    covering_lobs: list[str] = Field(default_factory=list)


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
        groups=list(user.groups),
        lob=user.lob,
        supervisor_id=user.supervisor_id,
        covering_lobs=list(user.covering_lobs),
    )


def _directory_client(settings: Settings) -> ZitadelDirectoryClient:
    if not settings.zitadel_service_pat:
        raise RuntimeError("ZITADEL service PAT is not configured")
    base_url = (
        settings.zitadel_internal_url or settings.oidc_internal_url or settings.zitadel_url
    ).rstrip("/")
    host = settings.zitadel_host_header or (
        urlparse(settings.oidc_issuer_url).netloc if settings.oidc_issuer_url else None
    )
    client = ZitadelDirectoryClient(
        base_url=base_url,
        pat=settings.zitadel_service_pat,
        host_header=host or None,
    )
    try:
        return client.with_org()
    except Exception:
        logger.warning("directory client continuing without org header", exc_info=True)
        return client


def load_users(
    settings: Settings | None = None,
    *,
    force_refresh: bool = False,
) -> SeedFile:
    """Load the live user directory from ZITADEL (cached)."""
    global _CACHE, _CACHE_AT

    cfg = settings or default_settings
    ttl = 60.0
    now = time.monotonic()
    if not force_refresh and _CACHE is not None and (now - _CACHE_AT) < ttl:
        return _CACHE

    users = [_to_seed_user(user) for user in _directory_client(cfg).list_directory_users()]
    seed = SeedFile(
        defaults={
            "password": cfg.default_password,
            "email_domain": cfg.email_domain,
        },
        users=users,
    )
    _CACHE = seed
    _CACHE_AT = now
    return seed


def load_users_from_yaml(path: Path) -> SeedFile:
    """Parse seed YAML — for unit tests and seed-schema checks only."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeedFile.model_validate(raw)


def user_by_id(seed: SeedFile, user_id: str) -> SeedUser:
    for user in seed.users:
        if user.user_id == user_id:
            return user
    raise KeyError(f"unknown user_id in directory: {user_id}")


def build_instruction_payload(
    *,
    owning_lob: str = "FICC",
    instruction_type: str = "SINGLE_USE",
    currency: str = "USD",
) -> dict[str, Any]:
    effective = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = effective + timedelta(days=365)
    return {
        "instruction_type": instruction_type,
        "owning_lob": owning_lob,
        "wire_scope": "DOMESTIC",
        "currency": currency,
        "funding_account": {
            "account_id": f"DDA-{owning_lob}-01",
            "account_name": f"{owning_lob} Client Payments",
            "owning_lob": owning_lob,
        },
        "debtor": {"name": "Client Fund A", "postal_address": {"country": "US"}},
        "debtor_account": {
            "identification_scheme": "PROPRIETARY",
            "identification": f"DDA-{owning_lob}-01",
            "currency": "USD",
        },
        "debtor_agent": {
            "financial_institution": {
                "scheme": "CLEARING_SYSTEM",
                "identification": "021000021",
                "clearing_system_id": "USABA",
            }
        },
        "creditor": {"name": "Counterparty LLC", "postal_address": {"country": "US"}},
        "creditor_account": {
            "identification_scheme": "PROPRIETARY",
            "identification": "9988776655",
            "currency": "USD",
        },
        "creditor_agent": {
            "financial_institution": {
                "scheme": "CLEARING_SYSTEM",
                "identification": "011401533",
                "clearing_system_id": "USABA",
            }
        },
        "charge_bearer": "SHAR",
        "effective_date": effective.isoformat().replace("+00:00", "Z"),
        "end_date": end.isoformat().replace("+00:00", "Z"),
    }
