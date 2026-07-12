from __future__ import annotations

from unittest.mock import AsyncMock

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

    def test_policies_mode_prefers_eligibility(self) -> None:
        assert (
            infer_execution_strategy_heuristic(
                "Who can approve payment 20260705-FX-P-534?",
                mode="policies",
            )
            == "eligibility"
        )
        assert (
            infer_execution_strategy_heuristic(
                "What is the funding approval policy?",
                mode="policies",
            )
            == "hybrid"
        )

    def test_is_graph_structured_for_ranking(self) -> None:
        assert is_graph_structured_question(
            "Which user triggered the most policy denial alerts this week?",
            mode="events",
        )


class TestSelectiveRetrieval:
    @pytest.mark.asyncio
    async def test_graph_strategy_skips_vector(self, rag_service, mock_multimodal, mock_neo4j) -> None:
        mock_multimodal.search_vector = AsyncMock(return_value=[{"source": "vector"}])
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
        assert result.graph_result["rows"] == [{"total": 3}]

    @pytest.mark.asyncio
    async def test_vector_strategy_skips_graph(self, rag_service, mock_ml_client, mock_multimodal) -> None:
        mock_multimodal.search_vector = AsyncMock(return_value=[{"source": "vector"}])
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
        assert decision.path == "graph"
        mock_ml_client.route_query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_question_falls_back_on_error(self, mock_ml_client) -> None:
        mock_ml_client.route_query = AsyncMock(side_effect=RuntimeError("router down"))
        from chat_application.pipeline.route import route_question

        decision = await route_question(mock_ml_client, "How many alerts?", mode="events")
        assert decision.strategy == "graph"

    def test_router_decision_normalizes_legacy_strategy(self) -> None:
        decision = RouterDecision(strategy="vector", reasoning="legacy")
        assert decision.path == "vector"
        assert decision.retrieval_strategy == "vector"

    def test_router_decision_skill_path(self) -> None:
        decision = RouterDecision(path="skill", reasoning="create payment")
        assert decision.skill == "create_payment"
        assert decision.retrieval_strategy == "hybrid"


class TestGraphUnavailableShortCircuit:
    def test_short_circuit_when_graph_empty(self) -> None:
        from chat_application.pipeline.orchestrator import RagPipelineOrchestrator

        assert RagPipelineOrchestrator._should_short_circuit_graph_unavailable(
            "graph",
            {"cypher": None, "rows": [], "graph_unavailable": True},
        )
        assert RagPipelineOrchestrator._should_short_circuit_graph_unavailable(
            "graph",
            {"cypher": None, "rows": [], "cypher_provenance": "none"},
        )

    def test_no_short_circuit_for_hybrid_or_successful_empty(self) -> None:
        from chat_application.pipeline.orchestrator import RagPipelineOrchestrator

        assert not RagPipelineOrchestrator._should_short_circuit_graph_unavailable(
            "hybrid",
            {"cypher": None, "rows": [], "graph_unavailable": True},
        )
        assert not RagPipelineOrchestrator._should_short_circuit_graph_unavailable(
            "graph",
            {
                "cypher": "MATCH (n) RETURN count(n) AS total",
                "rows": [],
                "graph_unavailable": False,
            },
        )
        assert not RagPipelineOrchestrator._should_short_circuit_graph_unavailable(
            "graph",
            {"cypher": None, "rows": [{"total": 0}], "graph_unavailable": True},
        )

    @pytest.mark.asyncio
    async def test_ask_skips_gemini_when_graph_unavailable(
        self, rag_service, mock_ml_client, mock_neo4j
    ) -> None:
        mock_ml_client.route_query = AsyncMock(
            return_value=RouterDecision(strategy="graph", reasoning="structured count")
        )
        mock_neo4j.run_cypher = AsyncMock(side_effect=RuntimeError("neo4j down"))

        response = await rag_service.ask("How many alerts today?", [])

        mock_ml_client.synthesize_answer.assert_not_awaited()
        assert "couldn't retrieve Neo4j graph results" in response.answer
        assert response.routing is not None
        assert response.routing.answer_synthesis == "formatter"
        assert response.routing.intent_id == "graph.unavailable"
