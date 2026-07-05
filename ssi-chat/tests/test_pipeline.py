from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from chat_application.pipeline.heuristic_strategy import (
    heuristic_router_decision,
    infer_execution_strategy_heuristic,
    is_graph_structured_question,
)
from chat_application.pipeline.models import RouterDecision


class TestHeuristicStrategy:
    def test_count_question_routes_graph(self) -> None:
        assert infer_execution_strategy_heuristic("How many alerts today?", mode="events") == "graph"

    def test_why_question_routes_vector(self) -> None:
        assert infer_execution_strategy_heuristic(
            "Why was payment X denied by policy?",
            mode="events",
        ) == "vector"

    def test_eligibility_heuristic(self) -> None:
        decision = heuristic_router_decision(
            "Who can approve payment 20260705-FX-P-534?",
            mode="payments",
        )
        assert decision.strategy == "eligibility"
        assert decision.eligibility_target == "payment"

    def test_is_graph_structured_for_ranking(self) -> None:
        assert is_graph_structured_question(
            "Which user triggered the most policy denial alerts this week?",
            mode="events",
        )


class TestSelectiveRetrieval:
    @pytest.mark.asyncio
    async def test_graph_strategy_skips_vector(self, rag_service, mock_multimodal, mock_neo4j) -> None:
        mock_multimodal.search_vector = AsyncMock(return_value=[{"source": "vector"}])
        mock_multimodal.search_bm25 = AsyncMock(return_value=[{"source": "bm25"}])
        mock_neo4j.run_cypher = AsyncMock(return_value=[{"total": 3}])

        from chat_application.pipeline.retrieve import execute_selective_retrieval

        result = await execute_selective_retrieval(
            rag_service,
            message="How many alerts today?",
            mode="events",
            strategy="graph",
            limit=10,
            search_source="security_events",
            event_ids=[],
            entity_ids=[],
        )
        mock_multimodal.search_vector.assert_not_called()
        mock_multimodal.search_bm25.assert_not_called()
        assert result.graph_result["rows"] == [{"total": 3}]

    @pytest.mark.asyncio
    async def test_vector_strategy_skips_graph(self, rag_service, mock_ml_client, mock_multimodal) -> None:
        mock_multimodal.search_vector = AsyncMock(return_value=[{"source": "vector"}])
        mock_multimodal.search_bm25 = AsyncMock(return_value=[])
        rag_service._search_graph = AsyncMock(return_value={"cypher": None, "rows": [], "cypher_provenance": "none"})

        from chat_application.pipeline.retrieve import execute_selective_retrieval

        await execute_selective_retrieval(
            rag_service,
            message="Why was this denied?",
            mode="events",
            strategy="vector",
            limit=10,
            search_source="security_events",
            event_ids=[],
            entity_ids=[],
        )
        rag_service._search_graph.assert_not_called()
        mock_multimodal.search_vector.assert_called_once()


class TestRouteQuestion:
    @pytest.mark.asyncio
    async def test_route_question_uses_llm(self, mock_ml_client) -> None:
        mock_ml_client.route_query = AsyncMock(
            return_value=RouterDecision(strategy="graph", reasoning="count question")
        )
        from chat_application.pipeline.route import route_question

        decision = await route_question(mock_ml_client, "How many alerts?", mode="events")
        assert decision.strategy == "graph"
        mock_ml_client.route_query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_question_falls_back_on_error(self, mock_ml_client) -> None:
        mock_ml_client.route_query = AsyncMock(side_effect=RuntimeError("router down"))
        from chat_application.pipeline.route import route_question

        decision = await route_question(mock_ml_client, "How many alerts?", mode="events")
        assert decision.strategy == "graph"
