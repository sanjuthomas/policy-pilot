from datetime import datetime

from ilm.models.instruction import CashSettlementInstruction
from ilm.storage import (
    document_to_versioned_instruction,
    versioned_instruction_to_document,
)


def test_versioned_instruction_round_trip(sample_instruction: CashSettlementInstruction) -> None:
    valid_in = datetime(2025, 1, 15, 10, 30, 0)
    valid_out = datetime(2025, 6, 1, 0, 0, 0)

    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=2,
        valid_in=valid_in,
        valid_out=valid_out,
    )
    assert doc["instruction_id"] == sample_instruction.instruction_id
    assert doc["version_number"] == 2
    assert doc["in"] == "2025-01-15T10:30:00Z"
    assert doc["out"] == "2025-06-01T00:00:00Z"
    assert doc["status"] == "DRAFT"
    assert doc["wire_scope"] == "DOMESTIC"

    restored = document_to_versioned_instruction(doc)
    assert restored.version_number == 2
    assert restored.valid_in == valid_in
    assert restored.valid_out == valid_out
    assert restored.instruction.instruction_id == sample_instruction.instruction_id
    assert restored.instruction.owning_lob == "FICC"


def test_versioned_instruction_open_ended(sample_instruction: CashSettlementInstruction) -> None:
    valid_in = datetime(2025, 3, 1, 12, 0, 0)
    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=valid_in,
        valid_out=None,
    )
    assert doc["out"] is None

    restored = document_to_versioned_instruction(doc)
    assert restored.valid_out is None
    assert restored.valid_in == valid_in
