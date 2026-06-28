from __future__ import annotations

from unittest.mock import MagicMock

from chat_application.qdrant import QdrantSearchClient
from qdrant_client.http import models


class TestSourceFilter:
    def setup_method(self) -> None:
        self.client = QdrantSearchClient()

    def test_none_returns_none(self) -> None:
        assert self.client._source_filter(None) is None

    def test_security_events_filter(self) -> None:
        filt = self.client._source_filter("security_events")
        assert isinstance(filt, models.Filter)
        condition = filt.must[0]
        assert condition.key == "source"
        assert condition.match.any == [
            "instruction_security_event",
            "payment_security_event",
        ]

    def test_payment_filter(self) -> None:
        filt = self.client._source_filter("payment")
        condition = filt.must[0]
        assert condition.match.value == "payment_fact"

    def test_instruction_state_filter(self) -> None:
        filt = self.client._source_filter("instruction_state")
        condition = filt.must[0]
        assert condition.match.value == "instruction_state"


class TestToHit:
    def setup_method(self) -> None:
        self.client = QdrantSearchClient()

    def test_converts_scored_point(self) -> None:
        point = models.ScoredPoint(
            id="pt-1",
            version=1,
            score=0.87,
            payload={
                "event_id": "evt-1",
                "instruction_id": "inst-1",
                "search_text": "policy denied",
                "merged": {"action": "VIEW", "severity": "ALERT"},
                "security_event": {"event_id": "evt-1"},
            },
        )
        hit = self.client._to_hit(point, "vector")
        assert hit["source"] == "vector"
        assert hit["score"] == 0.87
        assert hit["event_id"] == "evt-1"
        assert hit["merged"]["action"] == "VIEW"
        assert hit["security_event"]["event_id"] == "evt-1"

    def test_handles_missing_payload(self) -> None:
        point = models.ScoredPoint(id="pt-2", version=1, score=0.1, payload=None)
        hit = self.client._to_hit(point, "bm25")
        assert hit["score"] == 0.1
        assert hit["merged"] == {}
        assert hit["search_text"] == ""


class TestSearchWithoutClient:
    def test_search_vector_returns_empty_when_disconnected(self) -> None:
        client = QdrantSearchClient()
        assert client.search_vector([0.1, 0.2], limit=5) == []

    def test_search_bm25_returns_empty_when_disconnected(self) -> None:
        client = QdrantSearchClient()
        assert client.search_bm25("query", limit=5) == []

    def test_fetch_by_event_id_returns_none_when_disconnected(self) -> None:
        client = QdrantSearchClient()
        assert client.fetch_by_event_id("evt-1") is None

    def test_has_collection_false_when_disconnected(self) -> None:
        client = QdrantSearchClient()
        assert client.has_collection() is False

    def test_close_is_safe_when_not_connected(self) -> None:
        client = QdrantSearchClient()
        client.close()


class TestSearchWithMockClient:
    def test_search_vector_delegates_to_client(self) -> None:
        client = QdrantSearchClient()
        mock_qdrant = MagicMock()
        point = models.ScoredPoint(
            id="1",
            version=1,
            score=0.5,
            payload={"event_id": "evt-1", "search_text": "x"},
        )
        mock_qdrant.collection_exists.return_value = True
        mock_qdrant.query_points.return_value = MagicMock(points=[point])
        client._client = mock_qdrant

        hits = client.search_vector([0.1], limit=3, source="instruction_state")
        assert len(hits) == 1
        assert hits[0]["source"] == "vector"
        mock_qdrant.query_points.assert_called_once()

    def test_fetch_by_instruction_id(self) -> None:
        client = QdrantSearchClient()
        mock_qdrant = MagicMock()
        record = MagicMock()
        record.payload = {
            "instruction_id": "inst-42",
            "search_text": "standing instruction",
        }
        mock_qdrant.collection_exists.return_value = True
        mock_qdrant.retrieve.return_value = [record]
        client._client = mock_qdrant

        hit = client.fetch_by_instruction_id("inst-42")
        assert hit is not None
        assert hit["source"] == "exact_instruction"
        assert hit["instruction_id"] == "inst-42"
