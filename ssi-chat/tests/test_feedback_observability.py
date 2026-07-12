from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from chat_application.feedback_observability import (
    ChatFeedbackContext,
    get_feedback_distribution,
    record_chat_feedback,
    reset_feedback_distribution,
)


class TestChatFeedbackContext:
    def test_from_payload_uses_explicit_strategy(self) -> None:
        feedback = ChatFeedbackContext.from_payload(
            rating="up",
            mode="events",
            path="neo4j_direct",
            cypher_provenance="predefined_yaml",
            answer_synthesis="formatter",
            retrieval_strategy="deterministic",
            user_id="comp-001",
        )
        assert feedback.retrieval_strategy == "deterministic"

    def test_from_payload_derives_strategy_when_missing(self) -> None:
        feedback = ChatFeedbackContext.from_payload(
            rating="down",
            mode="payments",
            path="eligibility",
            cypher_provenance="none",
            answer_synthesis="eligibility_api",
            retrieval_strategy=None,
            user_id="comp-002",
        )
        assert feedback.retrieval_strategy == "eligibility"


class TestFeedbackDistribution:
    def setup_method(self) -> None:
        reset_feedback_distribution()

    def teardown_method(self) -> None:
        reset_feedback_distribution()

    @patch("chat_application.feedback_observability.record_counter")
    def test_record_chat_feedback_tracks_strategy_satisfaction(self, mock_counter) -> None:
        record_chat_feedback(
            ChatFeedbackContext(
                rating="up",
                mode="events",
                path="neo4j_direct",
                cypher_provenance="predefined_yaml",
                answer_synthesis="formatter",
                retrieval_strategy="deterministic",
                user_id="comp-001",
            )
        )
        record_chat_feedback(
            ChatFeedbackContext(
                rating="up",
                mode="events",
                path="neo4j_direct",
                cypher_provenance="predefined_yaml",
                answer_synthesis="formatter",
                retrieval_strategy="deterministic",
                user_id="comp-001",
            )
        )
        record_chat_feedback(
            ChatFeedbackContext(
                rating="down",
                mode="events",
                path="full_rag",
                cypher_provenance="llm_graph_plan",
                answer_synthesis="gemini_full",
                retrieval_strategy="graph",
                user_id="comp-001",
            )
        )

        snapshot = get_feedback_distribution()
        assert snapshot.total == 3
        assert snapshot.up == 2
        assert snapshot.down == 1
        assert snapshot.by_strategy["deterministic"].satisfaction_rate == 1.0
        assert snapshot.by_strategy["graph"].satisfaction_rate == 0.0

        mock_counter.assert_called()
        attrs = mock_counter.call_args.kwargs["attributes"]
        assert attrs["chat.feedback_rating"] == "down"
        assert attrs["chat.retrieval_strategy"] == "graph"


class TestFeedbackEndpoint:
    def setup_method(self) -> None:
        reset_feedback_distribution()

    def teardown_method(self) -> None:
        reset_feedback_distribution()

    def test_feedback_endpoint_records_vote(self, test_client: TestClient) -> None:
        response = test_client.post(
            "/api/chat/feedback",
            headers={
                "Authorization": "Bearer test-token",
                "X-Session-Id": "session-1",
            },
            json={
                "rating": "up",
                "mode": "events",
                "path": "neo4j_direct",
                "cypher_provenance": "predefined_yaml",
                "answer_synthesis": "formatter",
                "retrieval_strategy": "deterministic",
                "intent_id": "events.alerts_today_count",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "recorded"}

        stats = test_client.get("/api/feedback-stats")
        assert stats.status_code == 200
        payload = stats.json()
        assert payload["total"] == 1
        assert payload["by_strategy"]["deterministic"]["up"] == 1
        assert payload["by_strategy"]["deterministic"]["satisfaction_rate"] == 1.0

    def test_feedback_requires_auth(self, test_client: TestClient) -> None:
        import chat_application.main as main_module
        from chat_application.dependencies import get_chat_subject

        main_module.app.dependency_overrides.pop(get_chat_subject, None)
        response = test_client.post(
            "/api/chat/feedback",
            json={
                "rating": "up",
                "mode": "events",
                "path": "neo4j_direct",
                "cypher_provenance": "predefined_yaml",
                "answer_synthesis": "formatter",
            },
        )
        assert response.status_code == 401

    def test_feedback_stats_empty(self, test_client: TestClient) -> None:
        response = test_client.get("/api/feedback-stats")
        assert response.status_code == 200
        assert response.json()["total"] == 0
