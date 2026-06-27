from unittest.mock import AsyncMock, patch

import pytest

from ilm.authorization import PolicyDecision
from ilm.models.api import Subject
from ilm.models.enums import LifecycleAction
from ilm.models.instruction import CashSettlementInstruction
from ilm.opa import OpaClient, PolicyDeniedError


def test_as_string_list() -> None:
    assert OpaClient._as_string_list(["a", 1]) == ["a", "1"]
    assert OpaClient._as_string_list("not-a-list") == []
    assert OpaClient._as_string_list(None) == []


def test_violation_codes() -> None:
    assert OpaClient._violation_codes({"A": True, "B": False, "C": True}) == ["A", "C"]
    assert OpaClient._violation_codes([]) == []
    assert OpaClient._violation_codes(None) == []


def test_build_payload(
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    client = OpaClient(base_url="http://opa.test")
    payload = client._build_payload(
        LifecycleAction.CREATE,
        sample_subject,
        sample_instruction,
    )
    assert payload["input"]["action"] == "CREATE"
    assert payload["input"]["subject"]["user_id"] == "alice.ficc"
    assert payload["input"]["instruction"]["status"] == "DRAFT"
    assert payload["input"]["account"]["owning_lob"] == "FICC"


@pytest.mark.asyncio
async def test_evaluate_allowed(
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    client = OpaClient(base_url="http://opa.test")
    with patch.object(client, "_post_data", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [True, ["has creator role"]]
        decision = await client.evaluate(
            LifecycleAction.CREATE,
            sample_subject,
            sample_instruction,
        )
    assert decision == PolicyDecision(
        allowed=True,
        allow_basis=["has creator role"],
        violations=[],
        is_alert=False,
    )
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_evaluate_denied_with_alert(
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    client = OpaClient(base_url="http://opa.test")
    with patch.object(client, "_post_data", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            False,
            {"ALERT_LOB_MISMATCH": True, "SELF_APPROVAL": True},
            True,
        ]
        decision = await client.evaluate(
            LifecycleAction.APPROVE,
            sample_subject,
            sample_instruction,
        )
    assert decision.allowed is False
    assert decision.violations == ["ALERT_LOB_MISMATCH", "SELF_APPROVAL"]
    assert decision.is_alert is True


@pytest.mark.asyncio
async def test_authorize_raises_on_deny(
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    client = OpaClient(base_url="http://opa.test")
    denied = PolicyDecision(
        allowed=False,
        allow_basis=[],
        violations=["MISSING_ROLE_INSTRUCTION_CREATOR"],
        is_alert=False,
    )
    with patch.object(client, "evaluate", new_callable=AsyncMock, return_value=denied):
        with pytest.raises(PolicyDeniedError, match="missing INSTRUCTION_CREATOR role"):
            await client.authorize(
                LifecycleAction.CREATE,
                sample_subject,
                sample_instruction,
            )


@pytest.mark.asyncio
async def test_is_allowed(
    sample_subject: Subject,
    sample_instruction: CashSettlementInstruction,
) -> None:
    client = OpaClient(base_url="http://opa.test")
    allowed = PolicyDecision(allowed=True, allow_basis=[], violations=[], is_alert=False)
    with patch.object(client, "evaluate", new_callable=AsyncMock, return_value=allowed):
        assert await client.is_allowed(
            LifecycleAction.VIEW,
            sample_subject,
            sample_instruction,
        )
