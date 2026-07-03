from dataclasses import dataclass
from datetime import datetime
from typing import Any

from inst.constants import INSTRUCTION_CURRENT_OUT
from inst.models.instruction import CashSettlementInstruction


@dataclass(frozen=True)
class VersionedInstruction:
    instruction: CashSettlementInstruction
    version_number: int
    valid_in: datetime
    valid_out: datetime | None


def instruction_document_key(instruction_id: str, version_number: int) -> str:
    return f"{instruction_id}|{version_number}"


def instruction_id_from_document_key(document_key: str) -> str:
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


def _payload_without_instruction_id(instruction: CashSettlementInstruction) -> dict[str, Any]:
    payload = instruction.model_dump(mode="json")
    payload.pop("instruction_id", None)
    return payload


def versioned_instruction_to_document(
    instruction: CashSettlementInstruction,
    *,
    version_number: int,
    valid_in: datetime,
    valid_out: str | None = None,
) -> dict[str, Any]:
    out_value = valid_out if valid_out is not None else INSTRUCTION_CURRENT_OUT
    return {
        "_id": instruction_document_key(instruction.instruction_id, version_number),
        "version_number": version_number,
        "in": _format_timestamp(valid_in),
        "out": out_value,
        "status": instruction.status.value,
        "owning_lob": instruction.owning_lob,
        "wire_scope": instruction.wire_scope.value,
        "payload": _payload_without_instruction_id(instruction),
    }


def document_to_versioned_instruction(document: dict[str, Any]) -> VersionedInstruction:
    document_key = document["_id"]
    if isinstance(document_key, dict):
        instruction_id = str(document_key["id"])
    else:
        instruction_id = instruction_id_from_document_key(str(document_key))

    payload = dict(document.get("payload", document))
    payload.pop("_id", None)
    payload["instruction_id"] = instruction_id
    instruction = CashSettlementInstruction.model_validate(payload)

    out_raw = document.get("out")
    valid_out = (
        None
        if out_raw == INSTRUCTION_CURRENT_OUT
        else _parse_timestamp(out_raw)
    )

    return VersionedInstruction(
        instruction=instruction,
        version_number=document["version_number"],
        valid_in=_parse_timestamp(document["in"]) or instruction.created_at,
        valid_out=valid_out,
    )
