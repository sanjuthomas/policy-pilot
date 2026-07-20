from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from cypher_builder import GraphIntent, GraphQueryPlan
from tests.fixtures.router_decisions import GRAPH, set_router_decision


class TestRagServiceAsk:
    """ask() tests that require an explicit fixture RouterDecision (issue #13)."""

    @pytest.mark.asyncio
    async def test_ask_with_event_uuid_triggers_exact_lookup(
        self, rag_service, mock_vector_search, mock_neo4j, mock_ml_client
    ) -> None:
        set_router_decision(mock_ml_client, GRAPH)
        event_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        mock_vector_search.fetch_by_event_id = AsyncMock(
            return_value={
                "source": "exact",
                "event_id": event_id,
                "summary": "exact",
                "merged": {"source": "instruction_security_event", "action": "VIEW"},
            }
        )
        mock_vector_search.search_vector = AsyncMock(return_value=[])
        mock_neo4j.lookup_instruction_for_event = AsyncMock(
            return_value=[{"event_id": event_id, "instruction_id": "inst-1"}]
        )
        mock_ml_client.synthesize_answer = AsyncMock(return_value="Found event.")

        response = await rag_service.ask(f"What about event {event_id}?", [], mode="events")
        assert "Found event" in response.answer
        mock_vector_search.fetch_by_event_id.assert_awaited_once_with(
            event_id, allowed_lobs=None
        )

    @pytest.mark.asyncio
    async def test_ask_payment_approval_synthesis(
        self, rag_service, mock_ml_client, mock_vector_search, mock_neo4j
    ) -> None:
        set_router_decision(mock_ml_client, GRAPH)
        pid = "9b3251c9-d28e-4ad5-9bf4-dbc3c4fc13d8"
        mock_vector_search.search_vector = AsyncMock(return_value=[])
        mock_vector_search.fetch_by_payment_id = AsyncMock(
            return_value={
                "source": "exact_payment",
                "payment_id": pid,
                "merged": {
                    "source": "payment_fact",
                    "payment_id": pid,
                    "approver_display": "Laurent, Sophie (pay-201)",
                    "status": "APPROVED",
                },
            }
        )
        mock_vector_search.fetch_payment_approve_events = AsyncMock(
            return_value=[
                {
                    "source": "exact_approve_payment_event",
                    "payment_id": pid,
                    "merged": {
                        "source": "payment_security_event",
                        "payment_id": pid,
                        "action": "APPROVE_PAYMENT",
                        "outcome": "success",
                        "actor_display": "Laurent, Sophie (pay-201)",
                        "timestamp": "2026-06-27T21:39:26.072387Z",
                        "authorization_summary": (
                            "Laurent, Sophie (pay-201) was allowed to APPROVE_PAYMENT because "
                            "role FUNDING_APPROVER; group MIDDLE_OFFICE"
                        ),
                        "authorization_basis": [
                            "role FUNDING_APPROVER",
                            "group MIDDLE_OFFICE",
                            "covers LOB FICC",
                            "amount 1e+06 within subject and absolute limits",
                            "not self-approval (creator is not approver)",
                            "approver does not report to payment creator",
                        ],
                    },
                }
            ]
        )
        mock_neo4j.run_cypher = AsyncMock(return_value=[])
        mock_ml_client.summarize_authorization_why = AsyncMock(
            return_value="Sophie Laurent was authorized as a funding approver covering FICC."
        )

        response = await rag_service.ask(
            f"Who approved the payment {pid}?",
            [],
            mode="payments",
        )
        assert response.answer.startswith("WHO:")
        assert "BASIS:" in response.answer
        assert "WHY:" in response.answer
        assert "role FUNDING_APPROVER" in response.answer
        assert "covers LOB FICC" in response.answer
        assert "amount $1 million within subject and absolute limits" in response.answer
        assert "1e+06" not in response.answer
        assert "Policy basis (" not in response.answer
        mock_ml_client.synthesize_answer.assert_not_called()


class TestRagServiceSearchHelpers:
    @pytest.mark.asyncio
    async def test_search_vector_handles_embed_failure(self, rag_service, mock_ml_client) -> None:
        mock_ml_client.embed = AsyncMock(side_effect=RuntimeError("embed down"))
        hits = await rag_service._search_vector("query", 5)
        assert hits == []

    @pytest.mark.asyncio
    async def test_search_graph_uses_planned_queries(self, rag_service, mock_neo4j) -> None:
        mock_neo4j.run_cypher = AsyncMock(return_value=[{"total": 5}])
        result = await rag_service._search_graph("How many alerts today?", mode="events")
        assert {"total": 5} in result["rows"]
        assert result.get("cypher")
        assert "count(e)" in result["cypher"]
        assert result.get("planned")
        assert result["planned"][0][0]  # label preserved for synthesize formatters

    @pytest.mark.asyncio
    async def test_search_graph_uses_vertex_plan_when_unmatched(
        self, rag_service, mock_ml_client, mock_neo4j
    ) -> None:
        mock_ml_client.extract_graph_query_plan = AsyncMock(
            return_value=GraphQueryPlan(
                intent=GraphIntent.SECURITY_EVENT_AGGREGATE,
                operation="count",
                time_window="today",
                domain="all",
                severity="ALERT",
            )
        )
        mock_neo4j.run_cypher = AsyncMock(return_value=[{"total": 2}])
        result = await rag_service._search_graph("unusual alert wording", mode="events")
        assert {"total": 2} in result["rows"]
        mock_ml_client.extract_graph_query_plan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_graph_returns_empty_when_no_plan(
        self, rag_service, mock_ml_client, mock_neo4j
    ) -> None:
        mock_ml_client.extract_graph_query_plan = AsyncMock(
            return_value=GraphQueryPlan(intent=GraphIntent.INSTRUCTION_LOOKUP)
        )
        result = await rag_service._search_graph("random question", mode="events")
        assert result["rows"] == []
        assert result.get("cypher") is None
        assert result.get("graph_unavailable") is True

    @pytest.mark.asyncio
    async def test_search_graph_marks_unavailable_on_plan_extraction_failure(
        self, rag_service, mock_ml_client
    ) -> None:
        mock_ml_client.extract_graph_query_plan = AsyncMock(
            side_effect=RuntimeError("vertex down")
        )
        result = await rag_service._search_graph(
            "unusual alert wording with no planned match",
            mode="events",
        )
        assert result["rows"] == []
        assert result.get("cypher") is None
        assert result.get("graph_unavailable") is True

    @pytest.mark.asyncio
    async def test_search_graph_marks_unavailable_on_query_failure(
        self, rag_service, mock_neo4j
    ) -> None:
        mock_neo4j.run_cypher = AsyncMock(side_effect=RuntimeError("neo4j down"))
        result = await rag_service._search_graph("How many alerts today?", mode="events")
        assert result["rows"] == []
        assert result.get("cypher") is None
        assert result.get("graph_unavailable") is True
        assert result.get("cypher_provenance") == "predefined_planned"
