from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SeedUser(BaseModel):
    user_id: str
    given_name: str
    family_name: str
    title: str
    roles: list[str]
    lob: str | None = None
    supervisor_id: str | None = None
    covering_lobs: list[str] = Field(default_factory=list)


class SeedFile(BaseModel):
    defaults: dict[str, str] = Field(default_factory=dict)
    users: list[SeedUser]


def load_users(path: Path) -> SeedFile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SeedFile.model_validate(raw)


def user_by_id(seed: SeedFile, user_id: str) -> SeedUser:
    for user in seed.users:
        if user.user_id == user_id:
            return user
    raise KeyError(f"unknown user_id in seed file: {user_id}")


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


def build_payment_payload(
    *,
    instruction_id: str,
    amount: float = 1_000_000.0,
    value_date: str | None = None,
) -> dict[str, Any]:
    """Minimal payload for POST /api/v1/payments."""
    if value_date is None:
        value_date = (date.today() + timedelta(days=1)).isoformat()
    return {
        "instruction_id": instruction_id,
        "amount": amount,
        "value_date": value_date,
    }
