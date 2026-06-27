import pytest
from ilm.models.api import CreateInstructionRequest, Subject
from pydantic import ValidationError


def test_subject_to_opa_subject_includes_optional_fields() -> None:
    subject = Subject(
        user_id="bob.fx",
        title="Director",
        lob="FX",
        roles=["INSTRUCTION_APPROVER"],
        groups=["MIDDLE_OFFICE"],
        supervisor_id="mgr.fx",
        delegated_by_roles=["INSTRUCTION_MARKER"],
    )
    payload = subject.to_opa_subject()
    assert payload["user_id"] == "bob.fx"
    assert payload["lob"] == "FX"
    assert payload["supervisor_id"] == "mgr.fx"
    assert payload["delegated_by_roles"] == ["INSTRUCTION_MARKER"]


def test_subject_to_opa_subject_omits_none_lob() -> None:
    subject = Subject(user_id="u", title="VP", roles=["INSTRUCTION_CREATOR"])
    payload = subject.to_opa_subject()
    assert "lob" not in payload
    assert payload["delegated_by_roles"] == []


def test_create_instruction_request_validates(sample_create_request: CreateInstructionRequest) -> None:
    assert sample_create_request.owning_lob == "FICC"
    assert sample_create_request.wire_scope.value == "DOMESTIC"


def test_create_instruction_request_rejects_invalid_lob() -> None:
    from tests.conftest import _domestic_payload

    payload = _domestic_payload(owning_lob="NOT_A_LOB")
    with pytest.raises(ValidationError):
        CreateInstructionRequest.model_validate(payload)
