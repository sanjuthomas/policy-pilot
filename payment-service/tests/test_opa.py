from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from ps.authorization import PolicyDecision
from ps.models.enums import PaymentAction
from ps.opa import OpaClient, PolicyDeniedError


def test_as_string_list_from_list() -> None:
    assert OpaClient._as_string_list(["a", 1]) == ["a", "1"]


def test_as_string_list_non_list_returns_empty() -> None:
    assert OpaClient._as_string_list("not-a-list") == []


def test_violation_codes_from_dict() -> None:
    payload = {"ALERT_FOO": True, "SELF_APPROVAL": True, "DISABLED": False}
    assert OpaClient._violation_codes(payload) == ["ALERT_FOO", "SELF_APPROVAL"]


def test_violation_codes_non_dict_returns_empty() -> None:
    assert OpaClient._violation_codes([]) == []


def test_build_payload(subject, payment) -> None:
    client = OpaClient(base_url="http://opa.test")
    payload = client._build_payload(
        PaymentAction.CREATE_PAYMENT,
        subject,
        payment,
        instruction_end_date="2026-12-31",
        instruction_status="STANDING",
    )
    assert payload["input"]["action"] == "CREATE_PAYMENT"
    assert payload["input"]["subject"]["user_id"] == "alice"
    assert payload["input"]["payment"]["instruction_end_date"] == "2026-12-31"


@pytest.mark.asyncio
async def test_evaluate_allowed(subject, payment) -> None:
    client = OpaClient(base_url="http://opa.test")

    async def fake_post(path: str, payload: dict) -> object:
        if path.endswith("/allow"):
            return True
        if path.endswith("/allow_basis"):
            return ["role check passed"]
        return None

    client._post_data = AsyncMock(side_effect=fake_post)  # type: ignore[method-assign]

    decision = await client.evaluate(
        PaymentAction.CREATE_PAYMENT,
        subject,
        payment,
        instruction_end_date="2026-12-31",
        instruction_status="STANDING",
    )
    assert decision.allowed is True
    assert decision.allow_basis == ["role check passed"]
    assert decision.violations == []
    assert decision.is_alert is False


@pytest.mark.asyncio
async def test_evaluate_denied(subject, payment) -> None:
    client = OpaClient(base_url="http://opa.test")

    async def fake_post(path: str, payload: dict) -> object:
        if path.endswith("/allow"):
            return False
        if path.endswith("/violations"):
            return {"SELF_APPROVAL": True}
        if path.endswith("/is_alert"):
            return False
        return None

    client._post_data = AsyncMock(side_effect=fake_post)  # type: ignore[method-assign]

    decision = await client.evaluate(
        PaymentAction.APPROVE_PAYMENT,
        subject,
        payment,
    )
    assert decision.allowed is False
    assert decision.violations == ["SELF_APPROVAL"]
    assert decision.is_alert is False


@pytest.mark.asyncio
async def test_is_allowed_delegates_to_evaluate(subject, payment) -> None:
    client = OpaClient(base_url="http://opa.test")
    client.evaluate = AsyncMock(  # type: ignore[method-assign]
        return_value=PolicyDecision(True, [], [], False)
    )
    assert await client.is_allowed(
        PaymentAction.SUBMIT_PAYMENT,
        subject,
        payment,
        instruction_end_date="",
        instruction_status="STANDING",
    )


@pytest.mark.asyncio
async def test_authorize_raises_on_deny(subject, payment) -> None:
    client = OpaClient(base_url="http://opa.test")
    client.evaluate = AsyncMock(  # type: ignore[method-assign]
        return_value=PolicyDecision(
            False,
            [],
            ["ALERT_AMOUNT_EXCEEDS_100B_LIMIT"],
            True,
        )
    )
    with pytest.raises(PolicyDeniedError, match="100B"):
        await client.authorize(PaymentAction.CREATE_PAYMENT, subject, payment)


@pytest.mark.asyncio
async def test_authorize_returns_block_when_allowed(subject, payment) -> None:
    client = OpaClient(base_url="http://opa.test")
    client.evaluate = AsyncMock(  # type: ignore[method-assign]
        return_value=PolicyDecision(True, ["ok"], [], False)
    )
    block = await client.authorize(PaymentAction.CREATE_PAYMENT, subject, payment)
    assert block["decision"] == "allow"
    assert block["allow_basis"] == ["ok"]


@pytest.mark.asyncio
async def test_post_data_http_error() -> None:
    client = OpaClient(base_url="http://opa.test")

    with patch("ps.opa.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(
            return_value=httpx.Response(
                500,
                request=httpx.Request("POST", "http://opa.test/v1/data/payment/lifecycle/allow"),
            )
        )
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await client._post_data("payment/lifecycle/allow", {"input": {}})
