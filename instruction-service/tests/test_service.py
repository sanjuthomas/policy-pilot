from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from inst.authorization import PolicyDecision
from inst.config import settings
from inst.models.api import (
    CancelInstructionRequest,
    CreateInstructionRequest,
    RejectInstructionRequest,
    Subject,
    UseInstructionRequest,
)
from inst.models.enums import InstructionStatus, InstructionType, LifecycleAction
from inst.models.instruction import CashSettlementInstruction
from inst.service import InstructionService, InvalidStateTransitionError
from inst.storage import VersionedInstruction


def _allowed_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        allow_basis=["policy ok"],
        violations=[],
        is_alert=False,
    )


def _denied_decision(*, is_alert: bool = False) -> PolicyDecision:
    return PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["MISSING_ROLE_INSTRUCTION_CREATOR"],
        is_alert=is_alert,
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
def service(
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


def _versioned(instruction: CashSettlementInstruction, version: int = 1) -> VersionedInstruction:
    return VersionedInstruction(
        instruction=instruction,
        version_number=version,
        valid_in=datetime.utcnow(),
        valid_out=None,
    )


def _configure_repo_persist_mocks(mock_repo: MagicMock) -> None:
    """Echo persisted instructions so lifecycle_events from the service are preserved."""
    version_by_id: dict[str, int] = {}

    async def insert_initial(instruction, session=None):
        version_by_id[instruction.instruction_id] = 1
        return _versioned(instruction, version=1)

    async def append_version(instruction, session=None):
        current = version_by_id.get(instruction.instruction_id, 1)
        next_v = current + 1
        version_by_id[instruction.instruction_id] = next_v
        return _versioned(instruction, version=next_v)

    mock_repo.insert_initial = AsyncMock(side_effect=insert_initial)
    mock_repo.append_version = AsyncMock(side_effect=append_version)


@pytest.mark.asyncio
async def test_create_success(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.create(sample_create_request, sample_subject)

    assert response.instruction_id == "instr-001"
    mock_repo.insert_initial.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_denied_records_policy_denial(
    service: InstructionService,
    mock_authz: AsyncMock,
    mock_security_events: MagicMock,
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
) -> None:
    mock_authz.evaluate_instruction = AsyncMock(return_value=_denied_decision())

    with pytest.raises(PermissionError):
        await service.create(sample_create_request, sample_subject)

    mock_security_events.record_policy_denial.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_success(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    response = await service.get("instr-001", sample_subject)
    assert response.instruction_id == "instr-001"


@pytest.mark.asyncio
async def test_update_rejects_non_draft(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    submitted = sample_instruction.model_copy(update={"status": InstructionStatus.SUBMITTED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(submitted))

    with pytest.raises(InvalidStateTransitionError, match="DRAFT"):
        await service.update("instr-001", sample_create_request, sample_subject)


@pytest.mark.asyncio
async def test_cancel_cancels_draft(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.cancel(
                "instr-001",
                sample_subject,
                CancelInstructionRequest(reason="cleanup"),
            )

    assert response.status == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_cancels_submitted(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    submitted = sample_instruction.model_copy(update={"status": InstructionStatus.SUBMITTED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(submitted))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.cancel(
            "instr-001",
            sample_subject,
            CancelInstructionRequest(reason="withdrawn"),
        )

    assert response.status == "CANCELLED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        InstructionStatus.APPROVED,
        InstructionStatus.SUSPENDED,
        InstructionStatus.REJECTED,
        InstructionStatus.USED,
    ],
)
async def test_cancel_rejects_non_draft_or_submitted(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
    status: InstructionStatus,
) -> None:
    blocked = sample_instruction.model_copy(update={"status": status})
    mock_repo.get_current = AsyncMock(return_value=_versioned(blocked))

    with pytest.raises(InvalidStateTransitionError, match="DRAFT or SUBMITTED"):
        await service.cancel("instr-001", sample_subject)


@pytest.mark.asyncio
async def test_cancel_authorizes_before_status_change(
    service: InstructionService,
    mock_authz: AsyncMock,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        await service.cancel("instr-001", sample_subject)

    evaluate_call = mock_authz.evaluate_instruction.await_args
    assert evaluate_call is not None
    assert evaluate_call.kwargs["action"] == LifecycleAction.CANCEL.value
    assert evaluate_call.kwargs["instruction"]["status"] == InstructionStatus.DRAFT.value


@pytest.mark.asyncio
async def test_submit_transitions_to_submitted(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.submit("instr-001", sample_subject)

    assert response.status == "SUBMITTED"


@pytest.mark.asyncio
async def test_approve_standing(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    submitted = sample_instruction.model_copy(
        update={
            "status": InstructionStatus.SUBMITTED,
            "instruction_type": InstructionType.STANDING,
        }
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(submitted))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.approve("instr-001", sample_subject)

    assert response.status == "APPROVED"


@pytest.mark.asyncio
async def test_reject_submitted(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    submitted = sample_instruction.model_copy(update={"status": InstructionStatus.SUBMITTED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(submitted))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.reject(
                "instr-001",
                sample_subject,
                RejectInstructionRequest(reason="bad data"),
            )

    assert response.status == "REJECTED"
    assert response.rejection_reason == "bad data"


@pytest.mark.asyncio
async def test_suspend_active(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    active = sample_instruction.model_copy(update={"status": InstructionStatus.APPROVED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(active))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.suspend("instr-001", sample_subject)

    assert response.status == "SUSPENDED"


@pytest.mark.asyncio
async def test_reactivate_suspended(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    suspended = sample_instruction.model_copy(update={"status": InstructionStatus.SUSPENDED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(suspended))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.reactivate("instr-001", sample_subject)

    assert response.status == "APPROVED"


@pytest.mark.asyncio
async def test_use_single_use_marks_used(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    active = sample_instruction.model_copy(update={"status": InstructionStatus.APPROVED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(active))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.use(
                "instr-001",
                sample_subject,
                UseInstructionRequest(payment_reference="pay-123"),
            )

    assert response.status == "USED"
    assert response.usage_count == 1
    assert response.used_by == "pay-123"


@pytest.mark.asyncio
async def test_release_use_single_use_reverts_to_approved(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    used = sample_instruction.model_copy(
        update={
            "status": InstructionStatus.USED,
            "used_by": "pay-123",
            "usage_count": 1,
        }
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(used))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        from inst.models.api import ReleaseUseInstructionRequest

        response = await service.release_use(
            "instr-001",
            sample_subject,
            ReleaseUseInstructionRequest(payment_reference="pay-123"),
        )

    assert response.status == "APPROVED"
    assert response.used_by is None
    assert response.usage_count == 0


@pytest.mark.asyncio
async def test_release_use_rejects_payment_mismatch(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    used = sample_instruction.model_copy(
        update={
            "status": InstructionStatus.USED,
            "used_by": "pay-other",
            "usage_count": 1,
        }
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(used))

    from inst.models.api import ReleaseUseInstructionRequest

    with pytest.raises(InvalidStateTransitionError, match="used_by does not match"):
        await service.release_use(
            "instr-001",
            sample_subject,
            ReleaseUseInstructionRequest(payment_reference="pay-123"),
        )


@pytest.mark.asyncio
async def test_evaluate_policy_always_forwards_user_token(
    service: InstructionService,
    mock_authz: AsyncMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    obo_subject = sample_subject.model_copy(
        update={
            "delegated_by": "svc-payment",
            "delegated_by_roles": ["INSTRUCTION_VIEWER", "INSTRUCTION_MARKER"],
        }
    )
    with patch("inst.service.service_identity") as mock_identity:
        mock_identity.ensure_logged_in = AsyncMock()
        mock_identity.token = "svc-instruction-token"
        mock_identity.session_id = "svc-instruction-session"

        await service._evaluate_policy(
            LifecycleAction.USE,
            obo_subject,
            sample_instruction,
            bearer_token="user-token",
            session_id="user-session",
            authz_service_token="svc-payment-token",
            authz_service_session_id="svc-payment-session",
        )

    mock_authz.evaluate_instruction.assert_awaited_once()
    kwargs = mock_authz.evaluate_instruction.await_args.kwargs
    assert kwargs["user_token"] == "user-token"
    assert kwargs["user_session_id"] == "user-session"
    assert kwargs["service_token"] == "svc-payment-token"
    assert kwargs["subject"]["delegated_by"] == "svc-payment"
    assert "INSTRUCTION_MARKER" in kwargs["subject"]["delegated_by_roles"]


@pytest.mark.asyncio
async def test_evaluate_policy_requires_user_token(
    service: InstructionService,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    from inst.evaluate_tokens import (
        EvaluateTokenContext,
        bind_evaluate_token_context,
        reset_evaluate_token_context,
    )

    token = bind_evaluate_token_context(
        EvaluateTokenContext(user_token=None, user_session_id=None)
    )
    try:
        with pytest.raises(PermissionError, match="user token"):
            await service._evaluate_policy(
                LifecycleAction.VIEW,
                sample_subject,
                sample_instruction,
            )
    finally:
        reset_evaluate_token_context(token)


@pytest.mark.asyncio
async def test_list_skips_denied(
    service: InstructionService,
    mock_repo: MagicMock,
    mock_authz: AsyncMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.list_current = AsyncMock(return_value=[_versioned(sample_instruction)])
    mock_authz.evaluate_instruction = AsyncMock(
        side_effect=[_denied_decision(), _allowed_decision()]
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))

    visible = await service.list(sample_subject)
    assert visible == []


@pytest.mark.asyncio
async def test_should_record_security_event_excludes_configured_users(
    sample_subject: Subject,
) -> None:
    assert InstructionService._should_record_security_event(sample_subject) is True
    excluded = sample_subject.model_copy(update={"user_id": "excluded-svc"})
    with patch.object(settings, "security_event_excluded_user_ids", "excluded-svc"):
        assert InstructionService._should_record_security_event(excluded) is False


@pytest.mark.asyncio
async def test_should_record_view_security_event_excludes_admin(
    sample_subject: Subject,
) -> None:
    admin = sample_subject.model_copy(
        update={"user_id": "admin-001", "roles": ["PLATFORM_ADMIN"]}
    )
    assert InstructionService._should_record_view_security_event(admin) is False
    assert InstructionService._should_record_view_security_event(sample_subject) is True


@pytest.mark.asyncio
async def test_list_skips_view_security_events_for_admin(
    service: InstructionService,
    mock_repo: MagicMock,
    mock_security_events: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    admin = sample_subject.model_copy(
        update={"user_id": "admin-001", "roles": ["PLATFORM_ADMIN"]}
    )
    mock_repo.list_current = AsyncMock(return_value=[_versioned(sample_instruction)])

    visible = await service.list(admin)

    assert len(visible) == 1
    mock_security_events.record_authorized_action.assert_not_called()
    mock_security_events.record_policy_denial.assert_not_called()


@pytest.mark.asyncio
async def test_get_skips_view_security_events_for_admin(
    service: InstructionService,
    mock_repo: MagicMock,
    mock_security_events: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    admin = sample_subject.model_copy(
        update={"user_id": "admin-001", "roles": ["PLATFORM_ADMIN"]}
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))

    response = await service.get("instr-001", admin)

    assert response.instruction_id == "instr-001"
    mock_security_events.record_authorized_action.assert_not_called()


@pytest.mark.asyncio
async def test_record_authorized_action_skips_view_for_admin(
    service: InstructionService,
    mock_security_events: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    admin = sample_subject.model_copy(
        update={"user_id": "admin-001", "roles": ["PLATFORM_ADMIN"]}
    )
    await service._record_authorized_action(
        LifecycleAction.VIEW,
        admin,
        sample_instruction,
        version_number=1,
    )
    mock_security_events.record_authorized_action.assert_not_called()


@pytest.mark.asyncio
async def test_update_draft_success(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.update("instr-001", sample_create_request, sample_subject)

    assert response.instruction_id == "instr-001"
    mock_repo.append_version.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_returns_visible_instructions(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.list_current = AsyncMock(return_value=[_versioned(sample_instruction)])
    visible = await service.list(sample_subject)
    assert len(visible) == 1
    assert visible[0].instruction_id == "instr-001"


@pytest.mark.asyncio
async def test_list_versions(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    v1 = _versioned(sample_instruction, version=1)
    v2 = _versioned(sample_instruction, version=2)
    mock_repo.get_current = AsyncMock(return_value=v2)
    mock_repo.list_versions = AsyncMock(return_value=[v1, v2])

    versions = await service.list_versions("instr-001", sample_subject)
    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[1].version_number == 2


@pytest.mark.asyncio
async def test_cancel_already_cancelled(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    cancelled = sample_instruction.model_copy(update={"status": InstructionStatus.CANCELLED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(cancelled))

    with pytest.raises(InvalidStateTransitionError, match="already cancelled"):
        await service.cancel("instr-001", sample_subject)


@pytest.mark.asyncio
async def test_cancel_rejects_non_draft_or_submitted_blocked_status(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    approved = sample_instruction.model_copy(update={"status": InstructionStatus.APPROVED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(approved))

    with pytest.raises(InvalidStateTransitionError, match="DRAFT or SUBMITTED"):
        await service.cancel("instr-001", sample_subject)


@pytest.mark.asyncio
async def test_create_sequence_allocation_failure(
    service: InstructionService,
    sample_create_request: CreateInstructionRequest,
    sample_subject: Subject,
) -> None:
    from sequence_client.errors import SequenceClientError

    service.sequence.next_instruction_id = AsyncMock(
        side_effect=SequenceClientError("unavailable")
    )
    with pytest.raises(RuntimeError, match="sequence allocation failed"):
        await service.create(sample_create_request, sample_subject)


@pytest.mark.asyncio
async def test_eligible_approvers(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_repo.get_current = AsyncMock(return_value=_versioned(sample_instruction))
    service.authz.eligible_instruction_approvers = AsyncMock(
        return_value={"instruction_id": "instr-001", "eligible": []}
    )

    with patch("inst.service.service_identity.ensure_logged_in", AsyncMock()):
        data = await service.eligible_approvers(
            "instr-001",
            bearer_token="user-token",
            session_id="user-sess",
        )

    assert data["instruction_id"] == "instr-001"
    service.authz.eligible_instruction_approvers.assert_awaited_once()
    kwargs = service.authz.eligible_instruction_approvers.await_args.kwargs
    assert kwargs["user_token"] == "user-token"
    assert kwargs["user_session_id"] == "user-sess"


@pytest.mark.asyncio
async def test_eligible_approvers_requires_user_token(
    service: InstructionService,
) -> None:
    with pytest.raises(PermissionError, match="user token"):
        await service.eligible_approvers("instr-001")


@pytest.mark.asyncio
async def test_approve_single_use(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    pending = sample_instruction.model_copy(
        update={
            "status": InstructionStatus.SUBMITTED,
            "instruction_type": InstructionType.SINGLE_USE,
        }
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(pending))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.approve("instr-001", sample_subject)

    assert response.status == "APPROVED"


@pytest.mark.asyncio
async def test_submit_rejects_non_draft(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    submitted = sample_instruction.model_copy(update={"status": InstructionStatus.SUBMITTED})
    mock_repo.get_current = AsyncMock(return_value=_versioned(submitted))

    with pytest.raises(InvalidStateTransitionError, match="DRAFT"):
        await service.submit("instr-001", sample_subject)


@pytest.mark.asyncio
async def test_use_standing_increments_usage_without_used_status(
    service: InstructionService,
    mock_repo: MagicMock,
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    active = sample_instruction.model_copy(
        update={"status": InstructionStatus.APPROVED, "instruction_type": InstructionType.STANDING}
    )
    mock_repo.get_current = AsyncMock(return_value=_versioned(active))
    _configure_repo_persist_mocks(mock_repo)

    with patch("inst.service.mongo_transaction") as mock_tx:
        mock_tx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_tx.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await service.use(
            "instr-001",
            sample_subject,
            UseInstructionRequest(payment_reference="pay-1"),
        )

    assert response.status == "APPROVED"
    assert response.usage_count == 1
