from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_up(self, test_client: TestClient) -> None:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "UP"}


class TestStatusEndpoint:
    def test_status_reports_dependencies(self, test_client: TestClient, mock_qdrant) -> None:
        mock_qdrant.has_collection.return_value = True
        response = test_client.get("/api/status")
        assert response.status_code == 200
        body = response.json()
        assert "ollama_chat_model" in body
        assert body["qdrant_collection_exists"] is True


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
                json={"message": "How many alerts today?", "mode": "events"},
            )

        assert response.status_code == 200
        assert response.json()["answer"] == "Two alerts today."

    def test_chat_503_when_rag_not_ready(self, test_client: TestClient) -> None:
        with patch("chat_application.main.rag_service", None):
            response = test_client.post(
                "/api/chat",
                json={"message": "hello"},
            )
        assert response.status_code == 503


class TestCypherGenerateEndpoint:
    def test_cypher_generate_validates_query(
        self,
        test_client: TestClient,
        mock_ollama,
    ) -> None:
        mock_ollama.generate_cypher = AsyncMock(
            return_value="MATCH (e:SecurityEvent) RETURN e LIMIT 1"
        )
        response = test_client.post(
            "/api/cypher/generate",
            json={"question": "List events", "mode": "events"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is True
        assert "MATCH" in body["cypher"]

    def test_cypher_generate_reports_invalid_query(
        self,
        test_client: TestClient,
        mock_ollama,
    ) -> None:
        mock_ollama.generate_cypher = AsyncMock(return_value="CREATE (n) RETURN n LIMIT 1")
        response = test_client.post(
            "/api/cypher/generate",
            json={"question": "bad", "mode": "events"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["error"] is not None


class TestIndexRoute:
    def test_root_serves_index_html(self, test_client: TestClient) -> None:
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
