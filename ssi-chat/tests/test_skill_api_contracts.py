"""Skill HTTP contracts pinned to payment/instruction service Pydantic models."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_service_src(service: str) -> None:
    src = REPO_ROOT / service / "src"
    path = str(src)
    if path not in sys.path:
        sys.path.insert(0, path)


_ensure_service_src("payment-service")
_ensure_service_src("instruction-service")

from chat_application.skills.instruction_client import InstructionClient  # noqa: E402
from chat_application.skills.payment_client import PaymentClient  # noqa: E402
from inst.models.api import InstructionResponse  # noqa: E402
from ps.models.api import CreatePaymentRequest, PaymentResponse  # noqa: E402


def _user_ref(user_id: str = "pay-101") -> dict:
    return {
        "user_id": user_id,
        "given_name": "Emily",
        "family_name": "Rodriguez",
        "title": "Analyst",
        "lob": "FICC",
        "roles": ["PAYMENT_CREATOR"],
        "supervisor_id": "pay-201",
    }


def _payment_response_payload() -> dict:
    return {
        "payment_id": "20260715-FICC-P-9",
        "version_number": 1,
        "record_in": "evt-1",
        "record_out": None,
        "instruction_id": "20260715-FICC-I-1",
        "instruction_version": 2,
        "status": "DRAFT",
        "amount": 12_000_000.0,
        "currency": "USD",
        "value_date": "2026-07-16",
        "owning_lob": "FICC",
        "instruction_type": "STANDING",
        "created_by": _user_ref(),
        "submitted_by": None,
        "approved_by": None,
        "rejected_by": None,
        "cancelled_by": None,
        "rejection_reason": None,
        "cancellation_reason": None,
        "created_at": "2026-07-15T12:00:00Z",
        "updated_at": "2026-07-15T12:00:00Z",
        "submitted_at": None,
        "approved_at": None,
        "rejected_at": None,
        "cancelled_at": None,
        "lifecycle_events": [],
    }


def _fi_agent(bic: str, name: str) -> dict:
    return {
        "financial_institution": {
            "scheme": "BICFI",
            "identification": bic,
            "name": name,
        }
    }


def _instruction_response_payload() -> dict:
    return {
        "instruction_id": "20260715-FICC-I-1",
        "version_number": 2,
        "record_in": "evt-i-1",
        "record_out": None,
        "instruction_type": "STANDING",
        "status": "APPROVED",
        "owning_lob": "FICC",
        "wire_scope": "INTERNATIONAL",
        "currency": "USD",
        "funding_account": {
            "account_id": "FUND001",
            "account_name": "Funding",
            "owning_lob": "FICC",
        },
        "initiating_party": None,
        "ultimate_debtor": None,
        "debtor": {"name": "Acme Debtor"},
        "debtor_account": {
            "identification_scheme": "IBAN",
            "identification": "GB00ACME0001",
        },
        "debtor_agent": _fi_agent("DEBTUS33", "Debtor Bank"),
        "debtor_agent_account": None,
        "instructing_agent": None,
        "instructed_agent": None,
        "previous_instructing_agents": [],
        "intermediary_agents": [],
        "creditor_agent": _fi_agent("CREDUS33", "Creditor Bank"),
        "creditor_agent_account": None,
        "creditor": {"name": "Globex Creditor"},
        "creditor_account": {
            "identification_scheme": "IBAN",
            "identification": "CH00GLOBEX0002",
        },
        "ultimate_creditor": None,
        "charge_bearer": "SHAR",
        "instructions_for_creditor_agent": [],
        "instructions_for_next_agent": [],
        "effective_date": "2026-01-01T00:00:00Z",
        "end_date": "2026-12-31T00:00:00Z",
        "created_by": {
            "user_id": "pay-101",
            "given_name": "Emily",
            "family_name": "Rodriguez",
            "title": "Analyst",
            "lob": "FICC",
            "roles": ["PAYMENT_CREATOR"],
            "supervisor_id": "pay-201",
        },
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "submitted_at": "2026-01-01T12:00:00Z",
        "approved_by": None,
        "approved_at": "2026-01-02T00:00:00Z",
        "rejected_by": None,
        "rejected_at": None,
        "rejection_reason": None,
        "cancelled_at": None,
        "suspended_by": None,
        "suspended_at": None,
        "last_used_at": None,
        "usage_count": 0,
        "used_by": None,
    }


def _async_client(response: httpx.Response):
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    return context, client


def test_create_payment_request_matches_payment_service_schema() -> None:
    payload = {
        "instruction_id": "20260715-FICC-I-1",
        "amount": 12_000_000.0,
        "value_date": "2026-07-16",
    }
    parsed = CreatePaymentRequest.model_validate(payload)
    assert parsed.instruction_id == payload["instruction_id"]
    assert parsed.amount == payload["amount"]
    assert set(CreatePaymentRequest.model_fields) == {
        "instruction_id",
        "amount",
        "value_date",
    }


def test_payment_response_fixture_validates_against_payment_service() -> None:
    parsed = PaymentResponse.model_validate(_payment_response_payload())
    assert parsed.payment_id.startswith("20260715")
    assert parsed.created_by.user_id == "pay-101"
    # SoD-relevant field must remain on the payment resource for APPROVE.
    assert "created_by" in PaymentResponse.model_fields


def test_instruction_response_fixture_validates_against_instruction_service() -> None:
    parsed = InstructionResponse.model_validate(_instruction_response_payload())
    assert parsed.status == "APPROVED"
    assert parsed.owning_lob == "FICC"
    for required in ("instruction_id", "status", "owning_lob", "end_date", "currency"):
        assert required in InstructionResponse.model_fields


@pytest.mark.asyncio
async def test_payment_client_posts_create_schema_and_parses_response() -> None:
    response = httpx.Response(
        201,
        json=_payment_response_payload(),
        request=httpx.Request("POST", "http://payment.test/api/v1/payments"),
    )
    context, mock_client = _async_client(response)
    with (
        patch(
            "chat_application.skills.payment_client.httpx.AsyncClient",
            return_value=context,
        ),
        patch("chat_application.skills.payment_client.service_identity") as identity,
    ):
        identity.token = "svc"
        identity.session_id = "svc-sess"
        identity.ensure_logged_in = AsyncMock()
        body = await PaymentClient("http://payment.test").create_payment(
            instruction_id="20260715-FICC-I-1",
            amount=12_000_000.0,
            value_date="2026-07-16",
            user_token="user-token",
            user_session_id="sess",
        )
    CreatePaymentRequest.model_validate(mock_client.post.await_args.kwargs["json"])
    parsed = PaymentResponse.model_validate(body)
    assert parsed.payment_id == "20260715-FICC-P-9"
    assert parsed.created_by.user_id == "pay-101"


@pytest.mark.asyncio
async def test_instruction_client_parses_instruction_service_response() -> None:
    response = httpx.Response(
        200,
        json=_instruction_response_payload(),
        request=httpx.Request(
            "GET", "http://instruction.test/api/v1/instructions/20260715-FICC-I-1"
        ),
    )
    context, _ = _async_client(response)
    with (
        patch(
            "chat_application.skills.instruction_client.httpx.AsyncClient",
            return_value=context,
        ),
        patch("chat_application.skills.instruction_client.service_identity") as identity,
    ):
        identity.token = "svc"
        identity.session_id = "svc-sess"
        identity.ensure_logged_in = AsyncMock()
        body = await InstructionClient("http://instruction.test").get_instruction(
            "20260715-FICC-I-1",
            user_token="user-token",
            user_session_id="sess",
        )
    parsed = InstructionResponse.model_validate(body)
    assert parsed.instruction_id == "20260715-FICC-I-1"
    assert parsed.status == "APPROVED"
