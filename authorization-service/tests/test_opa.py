from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from authz.models import PaymentRecord, Subject, UserReference
from authz.opa import OpaClient


@pytest.mark.asyncio
async def test_can_approve_payment_returns_basis() -> None:
    client = OpaClient(base_url="http://opa.test")
    payment = PaymentRecord(
        payment_id="p1",
        instruction_id="i1",
        instruction_version=1,
        status="SUBMITTED",
        amount=100.0,
        currency="USD",
        owning_lob="FICC",
        created_by=UserReference(user_id="pay-101"),
    )
    subject = Subject(user_id="pay-201", title="VP", roles=["FUNDING_APPROVER"])

    with patch.object(client, "_post_data", new_callable=AsyncMock) as post_data:
        post_data.side_effect = [True, ["has_role", "covers_lob"]]
        allowed, basis = await client.can_approve_payment(
            subject,
            payment,
            instruction_end_date="2027-01-01",
            instruction_status="APPROVED",
        )

    assert allowed is True
    assert basis == ["has_role", "covers_lob"]


@pytest.mark.asyncio
async def test_can_approve_payment_denied() -> None:
    client = OpaClient(base_url="http://opa.test")
    payment = PaymentRecord(
        payment_id="p1",
        instruction_id="i1",
        instruction_version=1,
        status="SUBMITTED",
        amount=100.0,
        currency="USD",
        owning_lob="FICC",
        created_by=UserReference(user_id="pay-101"),
    )
    subject = Subject(user_id="pay-202", title="VP", roles=["FUNDING_APPROVER"])

    with patch.object(client, "_post_data", new_callable=AsyncMock, return_value=False):
        allowed, basis = await client.can_approve_payment(
            subject,
            payment,
            instruction_end_date="2027-01-01",
            instruction_status="APPROVED",
        )

    assert allowed is False
    assert basis == []


@pytest.mark.asyncio
async def test_can_approve_instruction_returns_basis() -> None:
    client = OpaClient(base_url="http://opa.test")
    subject = Subject(user_id="ficc-300", title="Vice President", roles=["INSTRUCTION_APPROVER"], lob="FICC")
    opa_instruction = {
        "status": "SUBMITTED",
        "type": "STANDING",
        "owning_lob": "FICC",
        "effective_date": "2026-01-01T00:00:00Z",
        "end_date": "2027-01-01T00:00:00Z",
        "created_by": {"user_id": "ficc-101", "title": "Analyst", "supervisor_id": "ficc-201"},
        "suspended_by": None,
    }
    opa_account = {"owning_lob": "FICC"}

    with patch.object(client, "_post_data", new_callable=AsyncMock) as post_data:
        post_data.side_effect = [True, ["approval matrix"]]
        allowed, basis = await client.can_approve_instruction(
            subject,
            opa_instruction=opa_instruction,
            opa_account=opa_account,
        )

    assert allowed is True
    assert basis == ["approval matrix"]


@pytest.mark.asyncio
async def test_fetch_policy_summary_payment() -> None:
    client = OpaClient(base_url="http://opa.test")
    catalog = {
        "domain": "payment",
        "actions": {"APPROVE": {"title": "Funding approval", "narrative": "…", "requires": []}},
    }

    with patch.object(client, "_get_data", new_callable=AsyncMock, return_value=catalog) as get_data:
        result = await client.fetch_policy_summary("payment")

    assert result["domain"] == "payment"
    get_data.assert_awaited_once_with("payment/lifecycle/policy_summary")


@pytest.mark.asyncio
async def test_fetch_payment_amount_limits() -> None:
    client = OpaClient(base_url="http://opa.test")
    catalog = {
        "absolute_limit": 100_000_000_000,
        "club_limits": {"UP_TO_100_MILLION_CLUB": 100_000_000},
    }

    with patch.object(client, "_get_data", new_callable=AsyncMock, return_value=catalog) as get_data:
        result = await client.fetch_payment_amount_limits()

    assert result["absolute_limit"] == 100_000_000_000
    get_data.assert_awaited_once_with("payment/lifecycle/amount_limits_catalog")


@pytest.mark.asyncio
async def test_fetch_policy_summary_rejects_unknown_domain() -> None:
    client = OpaClient(base_url="http://opa.test")
    with pytest.raises(ValueError, match="unsupported policy domain"):
        await client.fetch_policy_summary("treasury")


@pytest.mark.asyncio
async def test_evaluate_payment_records_allow_metric() -> None:
    client = OpaClient(base_url="http://opa.test")
    subject = Subject(user_id="pay-201", title="VP", roles=["FUNDING_APPROVER"])

    with patch("authz.opa.record_opa_evaluation") as record, patch.object(
        client, "_post_data", new_callable=AsyncMock
    ) as post_data:
        post_data.side_effect = [True, ["has_role"]]
        decision = await client.evaluate_payment(
            action="APPROVE",
            subject=subject,
            payment={"status": "SUBMITTED"},
        )

    assert decision.allowed is True
    record.assert_called_once()
    kwargs = record.call_args.kwargs
    assert record.call_args.args[0] == "payment/lifecycle"
    assert kwargs["allowed"] is True
    assert kwargs["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_evaluate_instruction_records_deny_metric() -> None:
    client = OpaClient(base_url="http://opa.test")
    subject = Subject(user_id="mo-100", title="Analyst", roles=["INSTRUCTION_CREATOR"])

    with patch("authz.opa.record_opa_evaluation") as record, patch.object(
        client, "_post_data", new_callable=AsyncMock
    ) as post_data:
        post_data.side_effect = [False, {"end_date_expired": True}, False]
        decision = await client.evaluate_instruction(
            action="APPROVE",
            subject=subject,
            instruction={"status": "SUBMITTED"},
            account={"owning_lob": "FICC"},
        )

    assert decision.allowed is False
    assert decision.violations == ["end_date_expired"]
    record.assert_called_once()
    assert record.call_args.args[0] == "instruction/lifecycle"
    assert record.call_args.kwargs["allowed"] is False


def test_record_opa_evaluation_no_telemetry_is_noop() -> None:
    from authz.metrics import record_opa_evaluation

    # Telemetry is not configured under pytest, so this must be a safe no-op.
    record_opa_evaluation("payment/lifecycle", allowed=True, duration_ms=12.5)
    record_opa_evaluation("instruction/lifecycle", allowed=False, duration_ms=0.0)
