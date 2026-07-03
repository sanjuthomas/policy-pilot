from datetime import datetime

from inst.constants import INSTRUCTION_CURRENT_OUT
from inst.models.instruction import CashSettlementInstruction
from inst.storage import (
    document_to_versioned_instruction,
    instruction_document_key,
    instruction_id_from_document_key,
    versioned_instruction_to_document,
)


def test_versioned_instruction_round_trip(sample_instruction: CashSettlementInstruction) -> None:
    valid_in = datetime(2025, 1, 15, 10, 30, 0)
    valid_out = "2025-06-01T00:00:00Z"

    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=2,
        valid_in=valid_in,
        valid_out=valid_out,
    )
    assert doc["_id"] == instruction_document_key(sample_instruction.instruction_id, 2)
    assert "instruction_id" not in doc
    assert doc["version_number"] == 2
    assert doc["in"] == "2025-01-15T10:30:00Z"
    assert doc["out"] == valid_out
    assert doc["status"] == "DRAFT"
    assert doc["wire_scope"] == "DOMESTIC"
    assert "instruction_id" not in doc["payload"]

    restored = document_to_versioned_instruction(doc)
    assert restored.version_number == 2
    assert restored.valid_in == valid_in
    assert restored.valid_out == datetime(2025, 6, 1, 0, 0, 0)
    assert restored.instruction.instruction_id == sample_instruction.instruction_id
    assert restored.instruction.owning_lob == "FICC"


def test_versioned_instruction_current_out_sentinel(
    sample_instruction: CashSettlementInstruction,
) -> None:
    valid_in = datetime(2025, 3, 1, 12, 0, 0)
    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=valid_in,
    )
    assert doc["out"] == INSTRUCTION_CURRENT_OUT
    assert doc["_id"] == instruction_document_key(sample_instruction.instruction_id, 1)

    restored = document_to_versioned_instruction(doc)
    assert restored.valid_out is None
    assert restored.valid_in == valid_in


def test_instruction_id_from_document_key() -> None:
    assert instruction_id_from_document_key("20260702-FICC-I-1|3") == "20260702-FICC-I-1"


def test_document_to_versioned_instruction_object_id_key(
    sample_instruction: CashSettlementInstruction,
) -> None:
    from bson import ObjectId

    oid = ObjectId()
    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=datetime(2025, 3, 1, 12, 0, 0),
    )
    doc["_id"] = {"id": str(oid)}
    restored = document_to_versioned_instruction(doc)
    assert restored.instruction.instruction_id == str(oid)


def test_parse_timestamp_accepts_datetime() -> None:
    from inst.storage import _parse_timestamp

    ts = datetime(2025, 1, 1, 12, 0, 0)
    assert _parse_timestamp(ts) == ts
