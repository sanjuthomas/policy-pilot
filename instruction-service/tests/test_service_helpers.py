from datetime import datetime

from inst.models.api import CreateInstructionRequest, Subject
from inst.models.enums import InstructionStatus
from inst.models.instruction import UserReference
from inst.service import (
    _fmt_datetime,
    _instruction_from_request,
    _parse_datetime,
    _to_response,
)
from inst.storage import VersionedInstruction


def test_parse_datetime_z_suffix() -> None:
    parsed = _parse_datetime("2025-06-01T12:00:00Z")
    assert parsed == datetime(2025, 6, 1, 12, 0, 0)
    assert parsed.tzinfo is None


def test_fmt_datetime_none() -> None:
    assert _fmt_datetime(None) is None


def test_fmt_datetime_value() -> None:
    assert _fmt_datetime(datetime(2025, 1, 2, 3, 4, 5)) == "2025-01-02T03:04:05Z"


def test_instruction_from_request(
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
) -> None:
    instruction = _instruction_from_request(
        sample_create_request,
        sample_subject,
        instruction_id="custom-id",
    )
    assert instruction.instruction_id == "custom-id"
    assert instruction.status == InstructionStatus.DRAFT
    assert instruction.created_by.user_id == "alice.ficc"
    assert instruction.created_by.given_name == "Alice"
    assert instruction.owning_lob == "FICC"


def test_instruction_from_request_preserves_created_by(
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
    sample_user_reference: UserReference,
) -> None:
    instruction = _instruction_from_request(
        sample_create_request,
        sample_subject,
        created_by=sample_user_reference,
    )
    assert instruction.created_by.user_id == sample_user_reference.user_id


def test_to_response(sample_instruction) -> None:
    valid_in = datetime(2025, 1, 1, 0, 0, 0)
    record = VersionedInstruction(
        instruction=sample_instruction,
        version_number=3,
        valid_in=valid_in,
        valid_out=None,
    )
    response = _to_response(record)
    assert response.instruction_id == "instr-001"
    assert response.version_number == 3
    assert response.record_in == "2025-01-01T00:00:00Z"
    assert response.record_out is None
    assert response.status == "DRAFT"
    assert response.charge_bearer == "SHAR"
