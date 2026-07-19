from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat_application.observability.routing import (
    AnswerRouting,
    cypher_class_for_provenance,
    cypher_provenance_for_direct_intent,
    finalize_chat_response,
    format_routing_label,
    get_routing_distribution,
    log_answer_routing,
    question_fingerprint,
    record_answer_routing_metrics,
    reset_routing_distribution,
)
from tests.fixtures.router_decisions import GRAPH, set_router_decision


@pytest.fixture(autouse=True)
def _reset_routing_distribution() -> None:
    reset_routing_distribution()
    yield
    reset_routing_distribution()


class TestQuestionFingerprint:
    def test_stable_hash_and_length(self) -> None:
        length, digest = question_fingerprint("  How many alerts?  ")
        assert length == len("How many alerts?")
        assert len(digest) == 16
        assert question_fingerprint("How many alerts?")[1] == digest


class TestFormatRoutingLabel:
    def test_includes_intent_when_present(self) -> None:
        label = format_routing_label(
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            intent_id="instruction.creator_by_id",
        )
        assert "Neo4j direct" in label
        assert "Predefined Cypher (YAML)" in label
        assert "intent=instruction.creator_by_id" in label

    def test_direct_intent_provenance_mapping(self) -> None:
        assert cypher_provenance_for_direct_intent("instruction.creator_by_id") == "predefined_yaml"
        assert (
            cypher_provenance_for_direct_intent("planned_graph", source="planned")
            == "predefined_planned"
        )

    def test_cypher_class_groups_provenance(self) -> None:
        assert cypher_class_for_provenance("predefined_yaml") == "deterministic"
        assert cypher_class_for_provenance("predefined_planned") == "deterministic"
        assert cypher_class_for_provenance("llm_graph_plan") == "llm"
        assert cypher_class_for_provenance("none") == "none"


class TestAnswerRoutingMetrics:
    @patch("chat_application.observability.routing.record_histogram")
    @patch("chat_application.observability.routing.record_counter")
    def test_record_answer_routing_metrics(
        self,
        mock_record_counter,
        mock_record_histogram,
    ) -> None:
        routing = AnswerRouting(
            path="full_rag",
            cypher_provenance="llm_graph_plan",
            answer_synthesis="gemini_full",
            mode="events",
            retrieval_strategy="graph",
            retrieval_ms=42.0,
            generation_ms=120.5,
        )
        record_answer_routing_metrics(routing)

        counter_names = [call.args[1] for call in mock_record_counter.call_args_list]
        assert "chat.answer.count" in counter_names
        assert "chat.retrieval.route.count" in counter_names
        assert "chat.routing.path_decision.count" in counter_names
        assert "chat.cypher.route.count" in counter_names

        route_call = next(
            call for call in mock_record_counter.call_args_list if call.args[1] == "chat.cypher.route.count"
        )
        assert route_call.kwargs["attributes"]["chat.cypher_class"] == "llm"
        assert route_call.kwargs["attributes"]["chat.cypher_provenance"] == "llm_graph_plan"

        decision_call = next(
            call
            for call in mock_record_counter.call_args_list
            if call.args[1] == "chat.routing.path_decision.count"
        )
        assert decision_call.kwargs["attributes"] == {
            "chat.requested_path": "full_rag",
            "chat.executed_path": "full_rag",
            "chat.route_override": "false",
            "chat.mode": "events",
        }

        hist_names = [call.args[1] for call in mock_record_histogram.call_args_list]
        assert "chat.answer.retrieval.duration" in hist_names
        assert "chat.answer.generation.duration" in hist_names

    @patch("chat_application.observability.routing.record_histogram")
    @patch("chat_application.observability.routing.record_counter")
    def test_record_path_decision_metrics_when_overridden(
        self,
        mock_record_counter,
        mock_record_histogram,
    ) -> None:
        del mock_record_histogram
        routing = AnswerRouting(
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            mode="events",
            retrieval_strategy="deterministic",
            requested_path="graph",
        )
        record_answer_routing_metrics(routing)
        decision_call = next(
            call
            for call in mock_record_counter.call_args_list
            if call.args[1] == "chat.routing.path_decision.count"
        )
        assert decision_call.kwargs["attributes"] == {
            "chat.requested_path": "graph",
            "chat.executed_path": "neo4j_direct",
            "chat.route_override": "true",
            "chat.mode": "events",
        }

    @patch("chat_application.observability.routing.record_answer_routing_metrics")
    def test_finalize_chat_response_records_metrics(self, mock_record_metrics) -> None:
        finalize_chat_response(
            "Who created inst-1?",
            "events",
            answer="Creator is Alice.",
            retrieval_ms=5.0,
            generation_ms=0.0,
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            intent_id="instruction.creator_by_id",
        )
        mock_record_metrics.assert_called_once()
        routing = mock_record_metrics.call_args.args[0]
        assert routing.cypher_provenance == "predefined_yaml"
        assert cypher_class_for_provenance(routing.cypher_provenance) == "deterministic"


class TestFinalizeChatResponse:
    def test_populates_routing_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("INFO")
        response = finalize_chat_response(
            "How many alerts today?",
            "events",
            answer="There were 2 alerts.",
            retrieval_ms=12.0,
            generation_ms=0.0,
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            intent_id="events.alerts_today_count",
            cypher="MATCH (e) RETURN count(e)",
            graph_rows=[{"total": 2}],
        )
        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.retrieval_strategy == "deterministic"
        assert response.routing.cypher_provenance == "predefined_yaml"
        assert response.routing.answer_synthesis == "formatter"
        assert "events.alerts_today_count" in (response.routing.label or "")
        assert any("strategy=deterministic" in record.message for record in caplog.records)

    def test_log_answer_routing_extra_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level("INFO")
        routing = AnswerRouting(
            path="full_rag",
            cypher_provenance="llm_graph_plan",
            answer_synthesis="gemini_full",
            mode="payments",
            retrieval_strategy="graph",
            question_length=10,
            question_hash="abc123",
        )
        log_answer_routing(routing)
        record = next(r for r in caplog.records if "chat.answer.completed" in r.message)
        assert getattr(record, "chat.path", None) == "full_rag"
        assert getattr(record, "chat.retrieval_strategy", None) == "graph"
        assert getattr(record, "chat.cypher_provenance", None) == "llm_graph_plan"


class TestRequestedVsExecutedPath:
    def test_finalize_preserves_requested_path_when_overridden(self) -> None:
        response = finalize_chat_response(
            "Who created 20260703-FICC-I-1?",
            "events",
            answer="Walsh created it.",
            retrieval_ms=5.0,
            generation_ms=0.0,
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            intent_id="instruction.creator_by_id",
            requested_path="graph",
        )
        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.requested_path == "graph"
        assert response.routing.retrieval_strategy == "deterministic"
        snapshot = get_routing_distribution()
        assert snapshot.route_override_total == 1
        assert snapshot.route_honored_total == 0
        assert snapshot.by_path_pair == {"graph->neo4j_direct": 1}

    def test_finalize_clears_requested_path_when_same_as_executed(self) -> None:
        response = finalize_chat_response(
            "Who created 20260703-FICC-I-1?",
            "events",
            answer="Walsh created it.",
            retrieval_ms=5.0,
            generation_ms=0.0,
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            requested_path="neo4j_direct",
        )
        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.requested_path is None

    @pytest.mark.asyncio
    async def test_neo4j_direct_handler_records_requested_path(self) -> None:
        from chat_application.pipeline.handlers.base import HandlerContext
        from chat_application.pipeline.handlers.neo4j_direct import Neo4jDirectHandler
        from chat_application.pipeline.models import RouterDecision

        direct = MagicMock()
        direct.answer = "creator: Walsh"
        direct.cypher = "MATCH ..."
        direct.graph_rows = [{"instruction_id": "i1"}]
        direct.intent_id = "instruction.creator_by_id"
        direct.source = "yaml"

        service = MagicMock()
        service._try_neo4j_direct_answer = AsyncMock(return_value=direct)
        ctx = HandlerContext(
            service=service,
            message="Who created i1?",
            history=[],
            mode="events",
            decision=RouterDecision(path="graph", strategy="graph"),
            subject=None,
            capabilities=MagicMock(),
            bearer_token=None,
            session_id=None,
            started=0.0,
        )
        response = await Neo4jDirectHandler().handle(ctx)
        assert response is not None
        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.requested_path == "graph"


class TestRagRoutingIntegration:
    @pytest.mark.asyncio
    async def test_ask_neo4j_direct_includes_routing(
        self, rag_service, mock_ml_client, mock_vector_search, mock_neo4j
    ) -> None:
        set_router_decision(mock_ml_client, GRAPH)
        mock_neo4j.run_cypher = AsyncMock(
            return_value=[
                {
                    "instruction_id": "20260703-FICC-I-1",
                    "creator_display": "Walsh, Patricia (mo-010)",
                }
            ]
        )
        mock_vector_search.search_vector = AsyncMock(return_value=[])
        mock_ml_client.synthesize_answer = AsyncMock(return_value="should not be called")

        response = await rag_service.ask(
            "Who created 20260703-FICC-I-1?",
            [],
            mode="events",
        )

        assert response.routing is not None
        assert response.routing.path == "neo4j_direct"
        assert response.routing.retrieval_strategy == "deterministic"
        assert response.routing.cypher_provenance == "predefined_yaml"
        assert response.routing.answer_synthesis == "formatter"
        assert response.routing.intent_id == "instruction.creator_by_id"
        assert response.routing.requested_path == "graph"

    @pytest.mark.asyncio
    async def test_ask_full_rag_formatter_includes_routing(
        self, rag_service, mock_ml_client, mock_vector_search, mock_neo4j
    ) -> None:
        set_router_decision(mock_ml_client, GRAPH)
        rag_service._try_neo4j_direct_answer = AsyncMock(return_value=None)
        mock_vector_search.search_vector = AsyncMock(return_value=[])
        mock_neo4j.run_cypher = AsyncMock(return_value=[{"total": 0}])
        mock_ml_client.synthesize_answer = AsyncMock(return_value="unused")

        response = await rag_service.ask("How many alerts?", [], mode="events")

        assert response.routing is not None
        assert response.routing.path == "full_rag"
        assert response.routing.retrieval_strategy == "graph"
        assert response.routing.answer_synthesis == "formatter"
        assert response.routing.cypher_provenance == "predefined_planned"
