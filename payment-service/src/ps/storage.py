from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ps.constants import PAYMENT_CURRENT_OUT
from ps.models.payment import Payment


@dataclass(frozen=True)
class VersionedPayment:
    payment: Payment
    version_number: int
    valid_in: datetime
    valid_out: datetime | None


def payment_document_key(payment_id: str, version_number: int) -> str:
    return f"{payment_id}|{version_number}"


def payment_id_from_document_key(document_key: str) -> str:
    return document_key.rsplit("|", 1)[0]


def _format_timestamp(value: datetime) -> str:
    return value.isoformat() + "Z"


def _parse_timestamp(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).replace(tzinfo=None)


def _payload_without_payment_id(payment: Payment) -> dict[str, Any]:
    payload = payment.model_dump(mode="json")
    payload.pop("payment_id", None)
    return payload


def versioned_payment_to_document(
    payment: Payment,
    *,
    version_number: int,
    valid_in: datetime,
    valid_out: str | None = None,
) -> dict[str, Any]:
    out_value = valid_out if valid_out is not None else PAYMENT_CURRENT_OUT
    return {
        "_id": payment_document_key(payment.payment_id, version_number),
        "version_number": version_number,
        "in": _format_timestamp(valid_in),
        "out": out_value,
        "status": payment.status.value,
        "owning_lob": payment.owning_lob,
        "instruction_id": payment.instruction_id,
        "payload": _payload_without_payment_id(payment),
    }


def document_to_versioned_payment(document: dict[str, Any]) -> VersionedPayment:
    document_key = document["_id"]
    if isinstance(document_key, dict):
        payment_id = str(document_key["id"])
    else:
        payment_id = payment_id_from_document_key(str(document_key))

    payload = dict(document.get("payload", document))
    payload.pop("_id", None)
    payload["payment_id"] = payment_id
    payment = Payment.model_validate(payload)

    out_raw = document.get("out")
    valid_out = (
        None
        if out_raw == PAYMENT_CURRENT_OUT
        else _parse_timestamp(out_raw)
    )

    return VersionedPayment(
        payment=payment,
        version_number=document["version_number"],
        valid_in=_parse_timestamp(document["in"]) or payment.created_at,
        valid_out=valid_out,
    )
