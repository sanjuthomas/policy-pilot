from __future__ import annotations

import os

import pytest

from ilm.models.api import CreateInstructionRequest, Subject
from ilm.models.enums import InstructionStatus
from ilm.models.instruction import CashSettlementInstruction, UserReference
from ilm.service import _instruction_from_request
from tests.helpers import domestic_payload


@pytest.fixture(scope="session", autouse=True)
def disable_open_telemetry_for_tests() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"


@pytest.fixture
def sample_subject() -> Subject:
    return Subject(
        user_id="alice.ficc",
        given_name="Alice",
        family_name="Nguyen",
        title="Vice President",
        lob="FICC",
        roles=["INSTRUCTION_CREATOR", "MIDDLE_OFFICE"],
        groups=["MIDDLE_OFFICE"],
        supervisor_id="mgr.ficc",
    )


@pytest.fixture
def sample_user_reference() -> UserReference:
    return UserReference(
        user_id="alice.ficc",
        given_name="Alice",
        family_name="Nguyen",
        title="Vice President",
        lob="FICC",
        roles=["INSTRUCTION_CREATOR", "MIDDLE_OFFICE"],
        supervisor_id="mgr.ficc",
    )


@pytest.fixture
def sample_create_request() -> CreateInstructionRequest:
    return CreateInstructionRequest.model_validate(domestic_payload())


@pytest.fixture
def sample_instruction(
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
) -> CashSettlementInstruction:
    return _instruction_from_request(
        sample_create_request,
        sample_subject,
        instruction_id="instr-001",
        status=InstructionStatus.DRAFT,
    )
