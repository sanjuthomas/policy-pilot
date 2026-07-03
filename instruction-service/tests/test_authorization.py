from inst.authorization import (
    PolicyDecision,
    build_authorization_block,
    details_with_authorization,
    instruction_resource_context,
    subject_at_decision,
)
from inst.models.api import Subject
from inst.models.enums import LifecycleAction
from inst.models.instruction import CashSettlementInstruction


def test_build_authorization_block_allow(sample_subject: Subject) -> None:
    decision = PolicyDecision(
        allowed=True,
        allow_basis=["has INSTRUCTION_CREATOR role", "LOB matches"],
        violations=[],
        is_alert=False,
    )
    block = build_authorization_block(
        decision,
        sample_subject,
        LifecycleAction.CREATE,
    )
    assert block["decision"] == "allow"
    assert block["action"] == "CREATE"
    assert block["is_alert"] is False
    assert block["violations"] == []
    assert "was allowed to CREATE" in block["summary"]
    assert "has INSTRUCTION_CREATOR role" in block["summary"]


def test_build_authorization_block_allow_without_basis(sample_subject: Subject) -> None:
    decision = PolicyDecision(allowed=True, allow_basis=[], violations=[], is_alert=False)
    block = build_authorization_block(
        decision,
        sample_subject,
        LifecycleAction.VIEW,
    )
    assert block["decision"] == "allow"
    assert block["summary"] == "Nguyen, Alice (alice.ficc) was allowed to VIEW"


def test_build_authorization_block_deny_single_violation(sample_subject: Subject) -> None:
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["MISSING_ROLE_INSTRUCTION_CREATOR"],
        is_alert=False,
    )
    block = build_authorization_block(
        decision,
        sample_subject,
        LifecycleAction.CREATE,
    )
    assert block["decision"] == "deny"
    assert block["is_alert"] is False
    assert "missing INSTRUCTION_CREATOR role" in block["summary"]
    assert "also:" not in block["summary"]


def test_build_authorization_block_deny_multi_violation_alert_priority(
    sample_subject: Subject,
) -> None:
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=[
            "MISSING_ROLE_INSTRUCTION_APPROVER",
            "ALERT_LOB_MISMATCH",
            "SELF_APPROVAL",
        ],
        is_alert=True,
    )
    block = build_authorization_block(
        decision,
        sample_subject,
        LifecycleAction.APPROVE,
    )
    assert block["decision"] == "deny"
    assert block["is_alert"] is True
    assert block["violations"][1] == "ALERT_LOB_MISMATCH"
    assert "approver LOB does not match instruction LOB" in block["summary"]
    assert "also:" in block["summary"]


def test_subject_at_decision_includes_delegation(sample_subject: Subject) -> None:
    subject = sample_subject.model_copy(
        update={"delegated_by": "payment-service", "delegated_by_roles": ["INSTRUCTION_MARKER"]}
    )
    payload = subject_at_decision(subject)
    assert payload["delegated_by"] == "payment-service"
    assert payload["delegated_by_roles"] == ["INSTRUCTION_MARKER"]


def test_instruction_resource_context(sample_instruction: CashSettlementInstruction) -> None:
    ctx = instruction_resource_context(sample_instruction)
    assert ctx["instruction_id"] == "instr-001"
    assert ctx["owning_lob"] == "FICC"
    assert ctx["status"] == "DRAFT"
    assert ctx["created_by_user_id"] == "alice.ficc"


def test_details_with_authorization_merges() -> None:
    merged = details_with_authorization(
        {"reason": "test"},
        {"decision": "allow", "summary": "ok"},
    )
    assert merged["reason"] == "test"
    assert merged["authorization"]["decision"] == "allow"


def test_display_name_without_given_or_family_name() -> None:
    subject = Subject(user_id="bob", title="VP", roles=["INSTRUCTION_CREATOR"])
    decision = PolicyDecision(allowed=True, allow_basis=[], violations=[], is_alert=False)
    block = build_authorization_block(decision, subject, LifecycleAction.VIEW)
    assert block["summary"] == "bob was allowed to VIEW"
