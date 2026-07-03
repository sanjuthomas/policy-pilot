from __future__ import annotations

from chat_application.reranker import graph_rows_to_hits, rrf_merge


class TestRrfMerge:
    def test_merges_same_event_across_sources(self) -> None:
        vector_hits = [
            {
                "source": "vector",
                "event_id": "evt-1",
                "instruction_id": "inst-1",
                "merged": {"action": "APPROVE", "message": "ok"},
            }
        ]
        bm25_hits = [
            {
                "source": "bm25",
                "event_id": "evt-1",
                "instruction_id": "inst-1",
                "merged": {"action": "APPROVE"},
            }
        ]
        merged = rrf_merge([vector_hits, bm25_hits], k=60)
        assert len(merged) == 1
        assert merged[0].event_id == "evt-1"
        assert merged[0].sources == {"vector", "bm25"}
        assert merged[0].score > 0

    def test_sorts_by_combined_score(self) -> None:
        list_a = [{"source": "vector", "event_id": "a", "summary": "first"}]
        list_b = [{"source": "bm25", "event_id": "b", "summary": "second"}]
        merged = rrf_merge([list_a, list_b], k=1)
        assert merged[0].event_id == "a"
        assert merged[1].event_id == "b"

    def test_uses_instruction_id_when_no_event(self) -> None:
        hits = [{"source": "vector", "instruction_id": "inst-99", "summary": "state"}]
        merged = rrf_merge([hits])
        assert merged[0].key == "instruction:inst-99"

    def test_prefers_longer_summary(self) -> None:
        hits_a = [
            {
                "source": "vector",
                "event_id": "evt-1",
                "summary": "short",
            }
        ]
        hits_b = [
            {
                "source": "bm25",
                "event_id": "evt-1",
                "summary": "much longer summary text",
            }
        ]
        merged = rrf_merge([hits_a, hits_b])
        assert merged[0].summary == "much longer summary text"

    def test_summary_from_search_hit_merged_payload(self) -> None:
        hits = [
            {
                "source": "vector",
                "event_id": "evt-2",
                "merged": {"authorization_summary": "OPA allowed approver"},
            }
        ]
        merged = rrf_merge([hits])
        assert "OPA allowed approver" in merged[0].summary


class TestGraphRowsToHits:
    def test_converts_graph_row_with_event_id(self) -> None:
        rows = [
            {
                "event_id": "evt-1",
                "instruction_id": "inst-1",
                "action": "APPROVE",
            }
        ]
        hits = graph_rows_to_hits(rows)
        assert len(hits) == 1
        assert hits[0]["source"] == "neo4j"
        assert hits[0]["event_id"] == "evt-1"
        assert hits[0]["instruction_id"] == "inst-1"
        assert hits[0]["graph_row"] == rows[0]

    def test_extracts_instruction_from_nested_node(self) -> None:
        rows = [
            {
                "version": {"instruction_id": "inst-nested"},
                "actor_display": "User One",
            }
        ]
        hits = graph_rows_to_hits(rows)
        assert hits[0]["instruction_id"] == "inst-nested"

    def test_empty_rows(self) -> None:
        assert graph_rows_to_hits([]) == []
