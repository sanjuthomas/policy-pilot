from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_up(self, test_client: TestClient) -> None:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "UP"}


class TestChatEndpoint:
    def test_chat_returns_rag_response(
        self,
        test_client: TestClient,
        mock_ollama,
        mock_qdrant,
        mock_neo4j,
    ) -> None:
        from chat_application.models import ChatResponse, SourceHit

        fake_response = ChatResponse(
            answer="Two alerts today.",
            sources=[SourceHit(score=1.0, sources=["neo4j"], summary="alert")],
        )
        mock_rag = MagicMock()
        mock_rag.ask = AsyncMock(return_value=fake_response)

        with patch("chat_application.main.rag_service", mock_rag):
            response = test_client.post(
                "/api/chat",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Session-Id": "session-1",
                },
                json={"message": "How many alerts today?", "mode": "events"},
            )

        assert response.status_code == 200
        assert response.json()["answer"] == "Two alerts today."

    def test_chat_503_when_rag_not_ready(self, test_client: TestClient) -> None:
        with patch("chat_application.main.rag_service", None):
            response = test_client.post(
                "/api/chat",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Session-Id": "session-1",
                },
                json={"message": "hello"},
            )
        assert response.status_code == 503

    def test_chat_requires_auth(self, test_client: TestClient) -> None:
        import chat_application.main as main_module
        from chat_application.dependencies import get_compliance_subject

        main_module.app.dependency_overrides.pop(get_compliance_subject, None)
        response = test_client.post(
            "/api/chat",
            json={"message": "hello"},
        )
        assert response.status_code == 401


class TestIndexRoute:
    def test_root_serves_index_html(self, test_client: TestClient) -> None:
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
