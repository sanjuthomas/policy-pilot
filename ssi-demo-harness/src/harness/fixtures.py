from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field
from zitadel_directory import DirectoryCache, DirectoryUser, build_directory_client

from harness.config import Settings
from harness.config import settings as default_settings

_CACHE: DirectoryCache | None = None
_CACHE_SETTINGS_ID: int | None = None


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
    return SeedUser(**user.seed_fields())


def _directory_cache(cfg: Settings) -> DirectoryCache:
    global _CACHE, _CACHE_SETTINGS_ID
    settings_id = id(cfg)
    if _CACHE is None or _CACHE_SETTINGS_ID != settings_id:
        if not cfg.zitadel_service_pat:
            raise RuntimeError("ZITADEL service PAT is not configured")
        base_url = (
            cfg.zitadel_internal_url or cfg.oidc_internal_url or cfg.zitadel_url
        ).rstrip("/")
        host = cfg.zitadel_host_header or (
            urlparse(cfg.oidc_issuer_url).netloc if cfg.oidc_issuer_url else None
        )
        pat = cfg.zitadel_service_pat

        def _client():
            return build_directory_client(
                base_url=base_url,
                pat=pat or "",
                host_header=host or None,
            )

        _CACHE = DirectoryCache(_client, ttl_seconds=60.0)
        _CACHE_SETTINGS_ID = settings_id
    return _CACHE


def load_users(
    settings: Settings | None = None,
    *,
    force_refresh: bool = False,
) -> SeedFile:
    """Load the live user directory from ZITADEL (shared DirectoryCache)."""
    cfg = settings or default_settings
    users = [
        _to_seed_user(user)
        for user in _directory_cache(cfg).list_users(force_refresh=force_refresh)
    ]
    return SeedFile(
        defaults={
            "password": cfg.default_password,
            "email_domain": cfg.email_domain,
        },
        users=users,
    )


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
