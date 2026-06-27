from __future__ import annotations

from datetime import UTC, datetime, timedelta


def domestic_payload(*, owning_lob: str = "FICC") -> dict:
    """Harness-style domestic wire create payload."""
    effective = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = effective + timedelta(days=365)
    return {
        "instruction_type": "SINGLE_USE",
        "owning_lob": owning_lob,
        "wire_scope": "DOMESTIC",
        "currency": "USD",
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
