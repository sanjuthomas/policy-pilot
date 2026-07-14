from __future__ import annotations

from chat_application.models import SourceHit
from chat_application.routing_observability import (
    AnswerRouting,
    classify_retrieval_strategy,
    count_source_channels,
    finalize_chat_response,
    get_routing_distribution,
    log_answer_routing,
    reset_routing_distribution,
)
from fastapi.testclient import TestClient


class TestRetrievalStrategyClassification:
    def test_eligibility_path(self) -> None:
        assert (
            classify_retrieval_strategy(
                path="eligibility",
                cypher_provenance="none",
                answer_synthesis="eligibility_api",
            )
            == "eligibility"
        )

    def test_policy_directory_path(self) -> None:
        assert (
            classify_retrieval_strategy(
                path="policy_directory",
                cypher_provenance="none",
                answer_synthesis="policy_directory_api",
            )
            == "policy_directory"
        )

    def test_neo4j_direct_is_deterministic(self) -> None:
        assert (
            classify_retrieval_strategy(
                path="neo4j_direct",
                cypher_provenance="predefined_yaml",
                answer_synthesis="formatter",
            )
            == "deterministic"
        )

    def test_full_rag_with_graph_rows_is_graph(self) -> None:
        assert (
            classify_retrieval_strategy(
                path="full_rag",
                cypher_provenance="predefined_planned",
                answer_synthesis="formatter",
                graph_row_count=2,
            )
            == "graph"
        )

    def test_full_rag_vector_dominant_is_vector(self) -> None:
        assert (
            classify_retrieval_strategy(
                path="full_rag",
                cypher_provenance="none",
                answer_synthesis="gemini_full",
                source_channels={"vector": 4, "neo4j": 0, "exact": 0},
                graph_row_count=0,
            )
            == "vector"
        )


class TestSourceChannelCounts:
    def test_count_source_channels(self) -> None:
        sources = [
            SourceHit(score=1.0, sources=["vector"], summary="a"),
            SourceHit(score=0.8, sources=["neo4j"], summary="b"),
        ]
        assert count_source_channels(sources) == {
            "vector": 1,
            "neo4j": 1,
            "exact": 0,
        }


class TestRoutingDistributionTracker:
    def setup_method(self) -> None:
        reset_routing_distribution()

    def teardown_method(self) -> None:
        reset_routing_distribution()

    def test_distribution_increments_on_log(self) -> None:
        log_answer_routing(
            AnswerRouting(
                path="neo4j_direct",
                cypher_provenance="predefined_yaml",
                answer_synthesis="formatter",
                mode="events",
                retrieval_strategy="deterministic",
            )
        )
        log_answer_routing(
            AnswerRouting(
                path="full_rag",
                cypher_provenance="llm_graph_plan",
                answer_synthesis="gemini_full",
                mode="payments",
                retrieval_strategy="graph",
                source_channels={"vector": 2, "neo4j": 1, "exact": 0},
            )
        )

        snapshot = get_routing_distribution()
        assert snapshot.total == 2
        assert snapshot.by_strategy == {"deterministic": 1, "graph": 1}
        assert snapshot.by_path == {"neo4j_direct": 1, "full_rag": 1}
        assert snapshot.by_source_channel == {"vector": 2, "neo4j": 1}

    def test_finalize_populates_retrieval_strategy(self) -> None:
        response = finalize_chat_response(
            "Summarize alerts",
            "events",
            answer="Several alerts occurred.",
            sources=[SourceHit(score=1.0, sources=["vector"], summary="alert")],
            retrieval_ms=50.0,
            generation_ms=200.0,
            path="full_rag",
            cypher_provenance="none",
            answer_synthesis="gemini_full",
        )
        assert response.routing is not None
        assert response.routing.retrieval_strategy == "vector"


class TestRoutingStatsEndpoint:
    def setup_method(self) -> None:
        reset_routing_distribution()

    def teardown_method(self) -> None:
        reset_routing_distribution()

    def test_routing_stats_endpoint(self, test_client: TestClient) -> None:
        finalize_chat_response(
            "Who created payment 20260704-FICC-P-1?",
            "payments",
            answer="Bob created it.",
            retrieval_ms=10.0,
            generation_ms=0.0,
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
        )

        response = test_client.get("/api/routing-stats")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["by_strategy"]["deterministic"] == 1
