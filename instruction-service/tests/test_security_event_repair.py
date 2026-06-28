from unittest.mock import AsyncMock, patch

import pytest

from inst.authorization import PolicyDecision
from inst.models.enums import InstructionStatus, LifecycleAction
from inst.security_event_repair import (
    _instruction_for_opa_replay,
    _subject_from_actor,
    repair_security_event_authorization,
)


def test_subject_from_actor() -> None:
    subject = _subject_from_actor(
        {
            "user_id": "alice.ficc",
            "given_name": "Alice",
            "family_name": "Nguyen",
            "title": "VP",
            "lob": "FICC",
            "roles": ["INSTRUCTION_CREATOR"],
            "groups": ["MIDDLE_OFFICE"],
            "supervisor_id": "mgr.ficc",
            "delegated_by": "payment-service",
            "delegated_by_roles": ["INSTRUCTION_MARKER"],
        }
    )
    assert subject.user_id == "alice.ficc"
    assert subject.delegated_by == "payment-service"
    assert subject.delegated_by_roles == ["INSTRUCTION_MARKER"]


def test_instruction_for_opa_replay_approve(sample_instruction) -> None:
    snap = sample_instruction.model_dump(mode="json")
    snap["status"] = InstructionStatus.STANDING.value
    snap["approved_by"] = {"user_id": "approver", "title": "MD", "roles": ["A"]}
    snap["approved_at"] = "2025-01-01T00:00:00Z"

    rewound = _instruction_for_opa_replay(snap, LifecycleAction.APPROVE)
    assert rewound.status == InstructionStatus.PENDING
    assert rewound.approved_by is None
    assert rewound.approved_at is None


def test_instruction_for_opa_replay_use_single_use(sample_instruction) -> None:
    snap = sample_instruction.model_dump(mode="json")
    snap["instruction_type"] = "SINGLE_USE"
    snap["status"] = InstructionStatus.USED.value
    snap["usage_count"] = 1

    rewound = _instruction_for_opa_replay(snap, LifecycleAction.USE)
    assert rewound.status == InstructionStatus.SINGLE_USE
    assert rewound.usage_count == 0


@pytest.mark.asyncio
async def test_repair_skips_when_authorization_present() -> None:
    document = {"details": {"authorization": {"decision": "allow"}}}
    assert await repair_security_event_authorization(document) is None


@pytest.mark.asyncio
async def test_repair_skips_failure_outcome() -> None:
    document = {"details": {}, "event": {"outcome": "failure"}}
    assert await repair_security_event_authorization(document) is None


@pytest.mark.asyncio
async def test_repair_success(sample_instruction) -> None:
    document = {
        "event_id": "evt-1",
        "event": {"outcome": "success", "action": "CREATE"},
        "actor": {
            "user_id": "alice.ficc",
            "title": "VP",
            "roles": ["INSTRUCTION_CREATOR"],
            "lob": "FICC",
        },
        "instruction_snapshot": sample_instruction.model_dump(mode="json"),
        "details": {},
    }
    decision = PolicyDecision(
        allowed=True,
        allow_basis=["ok"],
        violations=[],
        is_alert=False,
    )
    mock_authz = AsyncMock()
    mock_authz.evaluate_instruction = AsyncMock(return_value=decision)

    with patch("inst.security_event_repair.service_identity") as mock_identity:
        mock_identity.token = "svc-token"
        mock_identity.session_id = "sess-1"
        mock_identity.ensure_logged_in = AsyncMock()
        repaired = await repair_security_event_authorization(document, authz=mock_authz)

    assert repaired is not None
    assert repaired["details"]["authorization"]["decision"] == "allow"
    assert repaired["event"]["reason"] is not None


@pytest.mark.asyncio
async def test_repair_returns_none_when_policy_denies(sample_instruction) -> None:
    document = {
        "event_id": "evt-2",
        "event": {"outcome": "success", "action": "SUBMIT"},
        "actor": {"user_id": "alice.ficc", "title": "VP", "roles": ["R"]},
        "instruction_snapshot": sample_instruction.model_dump(mode="json"),
        "details": {},
    }
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["INVALID_STATE_TRANSITION"],
        is_alert=False,
    )
    mock_authz = AsyncMock()
    mock_authz.evaluate_instruction = AsyncMock(return_value=decision)

    with patch("inst.security_event_repair.service_identity") as mock_identity:
        mock_identity.token = "svc-token"
        mock_identity.session_id = "sess-1"
        mock_identity.ensure_logged_in = AsyncMock()
        assert await repair_security_event_authorization(document, authz=mock_authz) is None
