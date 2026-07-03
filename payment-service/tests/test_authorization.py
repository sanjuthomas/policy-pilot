from __future__ import annotations

from ps.authorization import (
    PolicyDecision,
    build_authorization_block,
    details_with_authorization,
    payment_resource_context,
    subject_at_decision,
)
from ps.models.api import Subject
from ps.models.enums import PaymentAction
from ps.models.payment import Payment


def test_subject_at_decision_includes_all_fields(subject: Subject) -> None:
    payload = subject_at_decision(subject)
    assert payload["user_id"] == "alice"
    assert payload["given_name"] == "Alice"
    assert payload["family_name"] == "Smith"
    assert payload["title"] == "VP Finance"
    assert payload["roles"] == ["PAYMENT_CREATOR"]
    assert payload["groups"] == ["MIDDLE_OFFICE"]
    assert payload["covering_lobs"] == ["CORP", "RETAIL"]
    assert payload["lob"] == "CORP"
    assert payload["supervisor_id"] == "boss1"


def test_payment_resource_context_defaults(payment: Payment) -> None:
    ctx = payment_resource_context(payment)
    assert ctx["payment_id"] == payment.payment_id
    assert ctx["instruction_id"] == "instr-001"
    assert ctx["instruction_owning_lob"] == "CORP"
    assert ctx["instruction_status"] == "APPROVED"
    assert ctx["instruction_end_date"] == ""
    assert ctx["payment_amount"] == 1_000_000.0
    assert ctx["payment_currency"] == "USD"
    assert ctx["payment_status"] == "DRAFT"
    assert ctx["created_by_user_id"] == "alice"


def test_payment_resource_context_overrides(payment: Payment) -> None:
    ctx = payment_resource_context(
        payment,
        instruction_status="APPROVED",
        instruction_end_date="2026-12-31",
    )
    assert ctx["instruction_status"] == "APPROVED"
    assert ctx["instruction_end_date"] == "2026-12-31"


def test_build_authorization_block_allow_with_basis(subject: Subject) -> None:
    decision = PolicyDecision(
        allowed=True,
        allow_basis=["subject has PAYMENT_CREATOR role"],
        violations=[],
        is_alert=False,
    )
    block = build_authorization_block(
        decision,
        subject,
        PaymentAction.CREATE_PAYMENT,
        resource_context={"payment_id": "pay-1"},
    )
    assert block["engine"] == "opa"
    assert block["package"] == "payment.lifecycle"
    assert block["action"] == "CREATE_PAYMENT"
    assert block["decision"] == "allow"
    assert block["allow_basis"] == ["subject has PAYMENT_CREATOR role"]
    assert block["violations"] == []
    assert block["is_alert"] is False
    assert "Smith, Alice (alice)" in block["summary"]
    assert "subject has PAYMENT_CREATOR role" in block["summary"]
    assert block["resource_context"] == {"payment_id": "pay-1"}


def test_build_authorization_block_allow_without_basis(subject: Subject) -> None:
    decision = PolicyDecision(allowed=True, allow_basis=[], violations=[], is_alert=False)
    block = build_authorization_block(decision, subject, PaymentAction.SUBMIT_PAYMENT)
    assert block["decision"] == "allow"
    assert block["summary"] == "Smith, Alice (alice) was allowed to SUBMIT_PAYMENT"


def test_build_authorization_block_deny_single_violation(subject: Subject) -> None:
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["SELF_APPROVAL"],
        is_alert=False,
    )
    block = build_authorization_block(decision, subject, PaymentAction.APPROVE_PAYMENT)
    assert block["decision"] == "deny"
    assert block["violations"] == ["SELF_APPROVAL"]
    assert block["is_alert"] is False
    assert "payment creator cannot approve own payment" in block["summary"]


def test_build_authorization_block_deny_prefers_alert_violation(subject: Subject) -> None:
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["SELF_APPROVAL", "ALERT_AMOUNT_EXCEEDS_100B_LIMIT"],
        is_alert=True,
    )
    block = build_authorization_block(decision, subject, PaymentAction.CREATE_PAYMENT)
    assert "100B USD ceiling" in block["summary"]
    assert "also:" in block["summary"]
    assert block["is_alert"] is True


def test_build_authorization_block_deny_unknown_violation_code(subject: Subject) -> None:
    decision = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["CUSTOM_RULE"],
        is_alert=False,
    )
    block = build_authorization_block(decision, subject, PaymentAction.REJECT_PAYMENT)
    assert "custom rule" in block["summary"]


def test_build_authorization_block_display_name_user_id_only() -> None:
    subject = Subject(user_id="svc-user", title="Service Account", roles=["PAYMENT_CREATOR"])
    decision = PolicyDecision(allowed=True, allow_basis=[], violations=[], is_alert=False)
    block = build_authorization_block(decision, subject, PaymentAction.CREATE_PAYMENT)
    assert block["summary"] == "svc-user was allowed to CREATE_PAYMENT"


def test_details_with_authorization_merges_details() -> None:
    auth = {"decision": "allow", "summary": "ok"}
    merged = details_with_authorization({"reason": "test"}, auth)
    assert merged == {"reason": "test", "authorization": auth}


def test_details_with_authorization_none_details() -> None:
    auth = {"decision": "deny"}
    merged = details_with_authorization(None, auth)
    assert merged == {"authorization": auth}
