"""Issue #13: fixture RouterDecisions are the CI stand-in for Gemini routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat_application.pipeline.models import RouterDecision
from chat_application.pipeline.route import route_question
from tests.fixtures import router_decisions as fixtures
from tests.fixtures.router_decisions import (
    REQUIRED_PATH_FIXTURES,
    set_router_decision,
)


class TestRouterDecisionFixtures:
    def test_required_path_matrix_validates(self) -> None:
        for decision in REQUIRED_PATH_FIXTURES:
            assert isinstance(decision, RouterDecision)
            assert decision.path is not None

    def test_set_router_decision_wires_mock(self) -> None:
        client = MagicMock()
        set_router_decision(client, fixtures.VECTOR)
        assert client.route_query.return_value is fixtures.VECTOR


class TestRouteFallbackOnly:
    """Heuristics may run only when the LLM router fails — not as happy path."""

    @pytest.mark.asyncio
    async def test_route_falls_back_when_llm_raises(self) -> None:
        client = MagicMock()
        client.route_query = AsyncMock(side_effect=RuntimeError("gemini down"))
        decision = await route_question(
            client,
            "How many alerts today?",
            mode="events",
        )
        assert decision.retrieval_strategy == "graph"
        assert "heuristic fallback" in (decision.reasoning or "")

    @pytest.mark.asyncio
    async def test_route_honors_fixture_llm_decision(self) -> None:
        client = MagicMock()
        set_router_decision(client, fixtures.ELIGIBILITY_PAYMENT)
        decision = await route_question(
            client,
            "Who can approve payment 20260705-FX-P-534?",
            mode="payments",
        )
        assert decision.path == "eligibility"
        assert decision.eligibility_target == "payment"
