from __future__ import annotations

from types import SimpleNamespace

import pytest
from chat_application.cypher import (
    extract_uuids,
    is_count_question,
    load_graph_schema,
    normalize_read_only_cypher,
    plan_graph_queries,
    records_to_rows,
    row_summary,
    validate_read_only_cypher,
)

VALID_QUERY = """MATCH (e:SecurityEvent)
RETURN e.event_id
LIMIT 10"""


class TestValidateReadOnlyCypher:
    def test_accepts_valid_query(self) -> None:
        validate_read_only_cypher(VALID_QUERY)

    def test_rejects_empty_query(self) -> None:
        with pytest.raises(ValueError, match="empty query"):
            validate_read_only_cypher("   ")

    def test_rejects_oversized_query(self) -> None:
        huge = "MATCH (n) RETURN n LIMIT 1 /* " + ("x" * 5000) + " */"
        with pytest.raises(ValueError, match="exceeds"):
            validate_read_only_cypher(huge)

    def test_rejects_multi_statement(self) -> None:
        with pytest.raises(ValueError, match="multiple statements"):
            validate_read_only_cypher("MATCH (n) RETURN n LIMIT 1; MATCH (m) RETURN m LIMIT 1")

    def test_rejects_non_read_start(self) -> None:
        with pytest.raises(ValueError, match="must begin with"):
            validate_read_only_cypher("CALL db.labels() YIELD label RETURN label LIMIT 1")

    def test_rejects_write_keywords(self) -> None:
        with pytest.raises(ValueError, match="disallowed write keyword 'CREATE'"):
            validate_read_only_cypher("MATCH (n) CREATE (m:Node) RETURN n LIMIT 1")

    def test_ignores_keywords_inside_string_literals(self) -> None:
        query = """MATCH (n {name: 'DELETE me'})
RETURN n.name
LIMIT 1"""
        validate_read_only_cypher(query)

    def test_strips_line_comments(self) -> None:
        query = """// CREATE would be bad if not a comment
MATCH (n)
RETURN n
LIMIT 1"""
        validate_read_only_cypher(query)

    def test_rejects_write_procedures(self) -> None:
        query = (
            'MATCH (n) CALL apoc.periodic.iterate("MATCH (m) RETURN m", '
            '"SET m.x=1", {}) YIELD batches RETURN n LIMIT 1'
        )
        with pytest.raises(ValueError, match="write-capable procedure"):
            validate_read_only_cypher(query)

    def test_requires_limit_clause(self) -> None:
        with pytest.raises(ValueError, match="must include a LIMIT"):
            validate_read_only_cypher("MATCH (n) RETURN n")


class TestNormalizeReadOnlyCypher:
    def test_empty_returns_empty(self) -> None:
        assert normalize_read_only_cypher("") == ""

    def test_leaves_query_with_limit_unchanged(self) -> None:
        assert normalize_read_only_cypher(VALID_QUERY) == VALID_QUERY

    def test_appends_limit_to_aggregate_without_limit(self) -> None:
        query = "MATCH (e:SecurityEvent) RETURN count(e) AS total"
        result = normalize_read_only_cypher(query)
        assert result.endswith("LIMIT 1")
        assert "count(e)" in result

    def test_strips_trailing_semicolon_before_limit(self) -> None:
        query = "MATCH (e) RETURN count(e) AS total;"
        result = normalize_read_only_cypher(query)
        assert result.endswith("LIMIT 1")
        assert ";" not in result.rstrip("LIMIT 1")


class TestPlanGraphQueries:
    def test_count_alerts_today(self) -> None:
        planned = plan_graph_queries("How many alerts today?", mode="events")
        assert planned is not None
        labels = [label for label, _ in planned]
        assert "count" in labels
        assert "details" in labels
        assert "date()" in planned[0][1]

    def test_count_payment_alerts_this_week(self) -> None:
        planned = plan_graph_queries(
            "How many payment alerts in the past 7 days?",
            mode="events",
        )
        assert planned is not None
        assert "payment_id IS NOT NULL" in planned[0][1]
        assert "P7D" in planned[0][1]

    def test_ranking_denial_alerts(self) -> None:
        planned = plan_graph_queries(
            "Which users had the most policy denial alerts?",
            mode="events",
        )
        assert planned is not None
        assert planned[0][0] == "ranking"
        assert "alert_count" in planned[0][1]

    def test_instruction_subordinate_approver(self) -> None:
        planned = plan_graph_queries(
            "Does the approver directly report to the instruction creator?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "hierarchy_violations"
        assert "REPORTS_TO" in planned[0][1]

    def test_instruction_approval_lookup_by_uuid(self) -> None:
        iid = "2846a7c0-4734-4626-bb58-13a966f935a1"
        planned = plan_graph_queries(
            f"Who approved instruction {iid}?",
            mode="instructions",
        )
        assert planned is not None
        assert planned[0][0] == "approval_lookup"
        assert iid in planned[0][1]

    def test_non_count_question_returns_none(self) -> None:
        assert plan_graph_queries("List recent events", mode="events") is None


class TestExtractUuids:
    def test_extracts_unique_in_order(self) -> None:
        u1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        u2 = "11111111-2222-3333-4444-555555555555"
        text = f"event {u1} and again {u1} then {u2}"
        assert extract_uuids(text) == [u1, u2]

    def test_empty_when_no_uuids(self) -> None:
        assert extract_uuids("no ids here") == []


class TestIsCountQuestion:
    @pytest.mark.parametrize(
        "question",
        [
            "How many alerts today?",
            "What is the number of denials?",
            "Count of payment events",
            "Total number of instructions",
        ],
    )
    def test_detects_count_phrases(self, question: str) -> None:
        assert is_count_question(question) is True

    def test_non_count_question(self) -> None:
        assert is_count_question("Who approved this instruction?") is False


class TestRecordsToRows:
    def test_converts_neo4j_like_records(self) -> None:
        node = SimpleNamespace(items=lambda: [("event_id", "evt-1"), ("action", "APPROVE")])

        class Record:
            def keys(self):
                return ["event", "instruction_id"]

            def __getitem__(self, key):
                return {"event": node, "instruction_id": "inst-1"}[key]

        rows = records_to_rows([Record()])
        assert rows == [{"event": {"event_id": "evt-1", "action": "APPROVE"}, "instruction_id": "inst-1"}]

    def test_handles_list_of_nodes(self) -> None:
        child = SimpleNamespace(items=lambda: [("user_id", "u-1")])

        class Record:
            def keys(self):
                return ["users"]

            def __getitem__(self, key):
                return {"users": [child]}[key]

        rows = records_to_rows([Record()])
        assert rows[0]["users"] == [{"user_id": "u-1"}]


class TestRowSummary:
    def test_summarizes_nested_event_node(self) -> None:
        row = {
            "event": {
                "event_id": "evt-1",
                "action": "APPROVE",
                "severity": "INFO",
                "message": "Approved",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        }
        summary = row_summary(row)
        assert "APPROVE" in summary
        assert "Approved" in summary

    def test_fallback_key_value_summary(self) -> None:
        summary = row_summary({"user_id": "fx-201", "alert_count": 5})
        assert "user_id=fx-201" in summary
        assert "alert_count=5" in summary


class TestLoadGraphSchema:
    def test_returns_empty_when_missing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("GRAPH_MODEL_DIR", str(tmp_path))
        from chat_application.config import Settings

        settings = Settings()
        monkeypatch.setattr("chat_application.cypher.settings", settings)
        assert load_graph_schema() == ""

    def test_reads_schema_file(self, tmp_path, monkeypatch) -> None:
        schema_dir = tmp_path / "model"
        schema_dir.mkdir()
        schema_file = schema_dir / "relationships.cypher"
        schema_file.write_text("MATCH (n) RETURN n LIMIT 1", encoding="utf-8")
        monkeypatch.setenv("GRAPH_MODEL_DIR", str(schema_dir))
        from chat_application.config import Settings

        settings = Settings()
        monkeypatch.setattr("chat_application.cypher.settings", settings)
        assert load_graph_schema() == "MATCH (n) RETURN n LIMIT 1"
