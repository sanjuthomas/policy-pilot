from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from chat_application.rag import RagService
from cypher_builder import GraphIntent, GraphQueryPlan
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def disable_open_telemetry_for_tests() -> None:
    os.environ["OTEL_SDK_DISABLED"] = "true"


@pytest.fixture
def mock_ml_client():
    from chat_application.pipeline.heuristic_strategy import heuristic_router_decision

    client = MagicMock()
    client.dimension = 768
    client.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    client.warmup = AsyncMock()
    client.route_query = AsyncMock(
        side_effect=lambda question, *, mode="events": heuristic_router_decision(
            question, mode=mode
        )
    )
    client.extract_graph_query_plan = AsyncMock(
        return_value=GraphQueryPlan(intent=GraphIntent.SECURITY_EVENT_AGGREGATE)
    )
    client.synthesize_answer = AsyncMock(return_value="Synthesized answer.")
    client.summarize_authorization_why = AsyncMock(return_value="Policy allowed approval.")
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_multimodal():
    client = MagicMock()
    client.has_documents = AsyncMock(return_value=False)
    client.search_vector = AsyncMock(return_value=[])
    client.search_bm25 = AsyncMock(return_value=[])
    client.fetch_by_event_id = AsyncMock(return_value=None)
    client.fetch_by_instruction_id = AsyncMock(return_value=None)
    client.fetch_instruction_approve_events = AsyncMock(return_value=[])
    client.fetch_by_payment_id = AsyncMock(return_value=None)
    client.fetch_payment_approve_events = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_neo4j():
    client = MagicMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.run_cypher = AsyncMock(return_value=[])
    client.lookup_instruction_for_event = AsyncMock(return_value=[])
    return client


@pytest.fixture
def rag_service(mock_ml_client, mock_multimodal, mock_neo4j):
    return RagService(
        ml_client=mock_ml_client,
        multimodal=mock_multimodal,
        neo4j=mock_neo4j,
    )


@pytest.fixture
def compliance_subject():
    from chat_application.subject import Subject

    return Subject(
        user_id="comp-001",
        title="Compliance Analyst",
        roles=["COMPLIANCE_ANALYST"],
    )


@pytest.fixture
def test_client(mock_ml_client, mock_multimodal, mock_neo4j, compliance_subject):
    import chat_application.main as main_module
    from chat_application.dependencies import get_chat_subject

    main_module.ml_client = mock_ml_client
    main_module.multimodal_client = mock_multimodal
    main_module.neo4j_client = mock_neo4j
    main_module.rag_service = None

    main_module.app.dependency_overrides[get_chat_subject] = lambda: compliance_subject

    with TestClient(main_module.app) as client:
        yield client

    main_module.app.dependency_overrides.clear()
