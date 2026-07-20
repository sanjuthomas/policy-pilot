"""Issue #13: fixture RouterDecisions are the CI stand-in for Gemini routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from chat_application.pipeline.models import RouterDecision
from chat_application.pipeline.route import route_question
from tests.fixtures import router_decisions as fixtures
from tests.fixtures.router_decisions import REQUIRED_PATH_FIXTURES, set_router_decision


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
            "How many ALERT events happened today?",
            mode="events",
        )
        # Structured count → neo4j_direct (path is law) via heuristic + YAML match.
        assert decision.path == "neo4j_direct"
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

    @pytest.mark.asyncio
    async def test_route_clamps_graph_to_neo4j_direct_when_yaml_matches(self) -> None:
        client = MagicMock()
        set_router_decision(client, fixtures.GRAPH)
        decision = await route_question(
            client,
            "Who created 20260703-FICC-I-1?",
            mode="events",
        )
        assert decision.path == "neo4j_direct"
        assert "clamped neo4j_direct" in (decision.reasoning or "")

    @pytest.mark.asyncio
    async def test_route_does_not_clamp_vector_to_neo4j_direct(self) -> None:
        client = MagicMock()
        set_router_decision(client, fixtures.VECTOR)
        decision = await route_question(
            client,
            "Who created 20260703-FICC-I-1?",
            mode="events",
        )
        assert decision.path == "vector"
