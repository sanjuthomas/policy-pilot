"""Integration tests for DRAFT instruction updates (PUT /api/v1/instructions/{id})."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from inst.authorization import PolicyDecision
from inst.dependencies import get_subject
from inst.models.api import CreateInstructionRequest, Subject
from inst.models.enums import InstructionStatus, LifecycleAction
from inst.models.instruction import CashSettlementInstruction
from inst.routes import get_service, router
from inst.service import InstructionService

from tests.helpers import domestic_payload
from tests.test_service import _configure_repo_persist_mocks, _versioned


def _allowed_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        allow_basis=["policy ok"],
        violations=[],
        is_alert=False,
    )


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_current = AsyncMock()
    repo.list_versions = AsyncMock(return_value=[])
    repo.list_current = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_authz() -> AsyncMock:
    authz = AsyncMock()
    authz.evaluate_instruction = AsyncMock(return_value=_allowed_decision())
    return authz


@pytest.fixture
def mock_security_events() -> MagicMock:
    events = MagicMock()
    events.allocate_event_id = AsyncMock(return_value="instr-001-SE-1")
    events.record_policy_denial = AsyncMock()
    events.record_authorized_action = AsyncMock()
    events.insert_document = AsyncMock()
    events.publish = AsyncMock()
    return events


@pytest.fixture
def update_service(
    mock_repo: MagicMock,
    mock_authz: AsyncMock,
    mock_security_events: MagicMock,
) -> InstructionService:
    sequence_client = AsyncMock()
    sequence_client.next_instruction_id = AsyncMock(return_value="instr-001")
    return InstructionService(
        repository=mock_repo,
        authz_client=mock_authz,
        security_events=mock_security_events,
        sequence_client=sequence_client,
    )


@pytest.fixture
def update_api_client(
    sample_subject: Subject,
    update_service: InstructionService,
) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_subject] = lambda: sample_subject
    app.dependency_overrides[get_service] = lambda: update_service
    return TestClient(app)


@pytest.mark.asyncio
async def test_update_draft_persists_changed_fields_and_version(
    update_service: InstructionService,
    mock_repo: MagicMock,
    mock_authz: AsyncMock,
    mock_security_events: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    _configure_repo_persist_mocks(mock_repo)

    updated_request = CreateInstructionRequest.model_validate(domestic_payload(owning_lob="FX"))

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await update_service.update(
            "instr-001",
            updated_request,
            sample_subject,
        )

    assert response.instruction_id == "instr-001"
    assert response.owning_lob == "FX"
    assert response.version_number == 2
    assert response.status == InstructionStatus.DRAFT.value
    assert response.created_by.user_id == sample_instruction.created_by.user_id

    mock_repo.append_version.assert_awaited_once()
    persisted: CashSettlementInstruction = mock_repo.append_version.await_args.args[0]
    assert persisted.owning_lob == "FX"
    assert persisted.status == InstructionStatus.DRAFT
    assert persisted.created_by.user_id == sample_instruction.created_by.user_id
    assert any(
        event.action == LifecycleAction.UPDATE.value for event in persisted.lifecycle_events
    )

    mock_authz.evaluate_instruction.assert_awaited()
    assert mock_authz.evaluate_instruction.await_args.kwargs["action"] == LifecycleAction.UPDATE.value
    mock_security_events.insert_document.assert_awaited_once()


def test_put_update_draft_instruction_via_api(
    update_api_client: TestClient,
    mock_repo: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = update_api_client.put(
            "/api/v1/instructions/instr-001",
            json=domestic_payload(owning_lob="FX"),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["instruction_id"] == "instr-001"
    assert body["owning_lob"] == "FX"
    assert body["version_number"] == 2
    assert body["status"] == "DRAFT"
    assert body["created_by"]["user_id"] == sample_instruction.created_by.user_id


def test_put_update_rejects_non_draft_via_api(
    update_api_client: TestClient,
    mock_repo: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    submitted = sample_instruction.model_copy(update={"status": InstructionStatus.SUBMITTED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(submitted))

    response = update_api_client.put(
        "/api/v1/instructions/instr-001",
        json=domestic_payload(),
    )

    assert response.status_code == 409
    assert "DRAFT" in response.json()["detail"]
